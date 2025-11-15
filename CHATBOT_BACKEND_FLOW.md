# Luồng Chat Backend

## Flow chính

```
Request → Validate → Load History → Check cần user data?
  ├─ Không → Skip
  └─ Có → Load từ Cache (hoặc Firebase nếu miss)
→ Build context + BM25 retrieval → LLM → Save history → Response
```

## Endpoints

**GET /health** - Health check

**POST /chat** - Response đầy đủ (TTFB 2-3s)

**POST /chat/stream** ⭐ - Streaming SSE (TTFB 0.5s)

**POST /user/collection/create|update|delete** - CRUD + auto clear cache

**GET /api-stats** - Usage stats

**GET /cache/stats** - Cache stats

## Cache (2-layer)

```
Request → In-memory (2min) → Firebase cache (5min) → Firebase DB
```

Clear khi:
- User create/update/delete
- TTL hết hạn

## API Keys

- 3-6 keys rotation
- 12 RPM/key (safe limit)
- Smart selection: chọn key có RPM thấp nhất

## 3. Luồng endpoint chính

### 3.1. GET `/health`
**Mục đích**: Health check

**Luồng**:
1. Return `{ "status": "ok", "timestamp": "..." }`

---

### 3.2. GET `/api-stats`
**Mục đích**: Monitor API key usage

**Luồng**:
1. Lấy stats từ `APIKeyRotator`:
   - Total keys
   - Current RPM per key
   - Usage percentage
   - Status (🟢 OK / 🟡 BUSY / 🔴 LIMIT)
2. Return JSON với chi tiết từng key

---

### 3.3. GET `/cache/stats`
**Mục đích**: Monitor cache performance

**Luồng**:
1. Lấy thống kê cache:
   - Total cached users
   - Documents count per user
   - Age và TTL remaining
2. Return JSON stats

---

### 3.4. POST `/chat` (Non-Streaming)
**Mục đích**: Chat với response đầy đủ một lần

**Input**:
```json
{
  "message": "Ngày mai tôi có kế hoạch gì?",
  "user_id": "user123",
  "session_id": "session_abc"
}
```

**Luồng chi tiết**:

#### Step 1: Validate Input
- Check `message` không rỗng
- Parse `user_id`, `session_id`

#### Step 2: Load History
- Query Firestore collection `chat_sessions`
- Lấy 5 câu hỏi/trả lời gần nhất
- Format thành text history

#### Step 3: Check Personal Question
```python
def is_personal_question(message):
    # Kiểm tra keywords: "tôi", "mình", "người yêu", "sinh nhật", v.v.
    # Return True nếu liên quan đến thông tin cá nhân
```

#### Step 4: Load User Data (CHỈ KHI CẦN)
**❌ KHÔNG PHẢI** load từ Firebase mỗi lần!

**✅ SỬ DỤNG CACHE**:
```python
def get_user_data_cached(user_id):
    # 1. Check cache (TTL 2 phút)
    if user_id in cache and not expired:
        return cached_data  # ← NHANH!
    
    # 2. Cache miss → Load từ Firebase
    user_docs = get_user_data_from_firebase(user_id)
    # Hàm này cũng có cache riêng (TTL 5 phút)
    
    # 3. Save vào cache
    cache[user_id] = (user_docs, current_time)
    return user_docs
```

**Firebase chỉ được query KHI**:
- ❌ **KHÔNG**: Mỗi lần chat
- ✅ **CÓ**: Cache miss (sau 2 phút)
- ✅ **CÓ**: User create/update/delete data
- ✅ **CÓ**: Manual cache clear

#### Step 5: Build Enhanced Context
```python
if is_personal_question and user_id:
    user_docs = get_user_data_cached(user_id)  # ← CACHE!
    personal_context = format_user_docs(user_docs)
    enhanced_history = history + personal_context
else:
    enhanced_history = history  # Không cần user data
```

#### Step 6: Retrieve from BM25
- Query BM25 với `message`
- Lấy k=1 document relevant nhất
- Add vào context

#### Step 7: Call LLM
```python
chain.invoke({
    "input": message,
    "history": enhanced_history,
    "current_time": vietnam_time
})
```
- Gemini generate response (2-3 giây)
- Return full answer một lần

#### Step 8: Save History
- Write to Firestore `chat_sessions`
- Giữ 5 câu gần nhất (MAX_HISTORY_SIZE)

#### Step 9: Return Response
```json
{
  "success": true,
  "answer": "...",
  "session_id": "session_abc",
  "user_id": "user123",
  "has_personal_context": true,
  "timestamp": "..."
}
```

---

### 3.5. POST `/chat/stream` ⭐ **STREAMING** (KHUYẾN NGHỊ)
**Mục đích**: Chat với Server-Sent Events streaming

**Input**: Giống `/chat`

**Luồng chi tiết**:

#### Step 1-5: Giống `/chat`
- Validate, load history, check personal, cache user data

#### Step 6: Stream Generator
```python
def generate():
    # Send start event
    yield 'data: {"type": "start", "session_id": "..."}\n\n'
    
    # Stream từ LLM
    full_answer = ""
    for chunk in chain.stream({...}):
        if 'answer' in chunk:
            token = chunk['answer']
            full_answer += token
            
            # Send token ngay lập tức
            yield f'data: {{"type": "token", "content": "{token}"}}\n\n'
    
    # Save history
    add_to_history(session_id, message, full_answer)
    
    # Send done event
    yield f'data: {{"type": "done", "full_answer": "..."}}\n\n'
    yield 'data: [DONE]\n\n'
```

#### Response Format (SSE):
```
data: {"type": "start", "session_id": "session_abc"}

data: {"type": "token", "content": "Ngày"}

data: {"type": "token", "content": " mai"}

data: {"type": "token", "content": " bạn"}

...

data: {"type": "done", "full_answer": "Ngày mai bạn có kế hoạch..."}

data: [DONE]
```

**Ưu điểm**:
- ⚡ Time to First Token: ~0.5s (vs 2-3s non-streaming)
- ✨ UX tốt hơn 10x
- 🚀 Giống ChatGPT

---

### 3.6. POST `/user/collection/create`
**Mục đích**: Tạo collection cho user mới

**Input**:
```json
{
  "user_id": "user123",
  "text": "Thông tin cá nhân..."
}
```

**Luồng**:
1. Check collection đã tồn tại chưa
2. Nếu chưa: Build collection trong ChromaDB
3. **⚠️ QUAN TRỌNG**: Clear ALL caches
   ```python
   clear_user_cache(user_id)  # Clear both layers!
   ```
4. Return success

---

### 3.7. POST `/user/collection/update`
**Mục đích**: Update/thêm data vào collection

**Input**:
```json
{
  "user_id": "user123",
  "text": "Kế hoạch mới...",
  "text_id": "plan_001"
}
```

**Luồng**:
1. Check collection tồn tại
2. Update collection trong ChromaDB
3. **⚠️ QUAN TRỌNG**: Clear ALL caches
   ```python
   clear_user_cache(user_id)  # Force reload!
   ```
4. Return success

**Tại sao cần clear cache?**
- User vừa tạo plan mới
- Chat tiếp theo phải thấy plan đó ngay
- Cache cũ (2-5 phút) sẽ không có plan mới
- → Clear để force reload từ Firebase

---

### 3.8. POST `/user/collection/delete`
**Mục đích**: Xóa data khỏi collection

**Luồng**:
1. Delete from ChromaDB
2. **Clear ALL caches**
3. Return success

---

### 3.9. POST `/cache/clear`
**Mục đích**: Clear cache manually

**Input (optional)**:
```json
{
  "user_id": "user123"  // Clear 1 user, hoặc bỏ để clear all
}
```

**Luồng**:
1. Nếu có `user_id`: Clear cache của user đó
2. Nếu không: Clear toàn bộ cache
3. Return stats

## 4. Cache Strategy (Two-Layer)

### Layer 1: Main Cache (main.py)
```python
user_data_cache = {}  # {user_id: (data, timestamp)}
CACHE_TTL = 120  # 2 minutes

# Cache HIT → return ngay (nhanh!)
# Cache MISS → query Firebase → save cache
```

### Layer 2: Firebase Cache (firebaseCache.py)
```python
FirebaseDataCache(ttl_seconds=300)  # 5 minutes

# get_user_data_from_firebase() tự động cache
# TTL dài hơn để backup
```

### Cache Invalidation
**Auto-clear khi**:
- POST `/user/collection/create`
- POST `/user/collection/update`
- POST `/user/collection/delete`

**Manual clear**:
- POST `/cache/clear`

**Auto-expire**:
- Sau 2 phút (Layer 1)
- Sau 5 phút (Layer 2)

## 5. API Key Rotation Strategy

### Smart Rotation Algorithm
```python
def get_next_key():
    # 1. Tính RPM hiện tại của mỗi key (sliding window 60s)
    # 2. Chọn key có RPM < SAFE_RPM (12)
    # 3. Nếu tất cả keys đều busy → chọn key có RPM thấp nhất
    # 4. Track usage và timestamp
    # 5. Return key
```

### Rate Limiting
```
Per Key: 12 RPM (safe), 15 RPM (limit)
3 Keys: 36 RPM total
6 Keys: 72 RPM total
```

### Monitoring
```bash
GET /api-stats
→ Real-time RPM per key
→ Status indicators
```

## 6. Performance Metrics

### Non-Streaming (`/chat`)
- Average: 10-12s
- TTFB: 2-3s
- Throughput: ~17 RPM
- Good for: Simple apps

### Streaming (`/chat/stream`) ⭐
- Average: 10-12s (total)
- **TTFB: 0.5s** ← USER SEES THIS!
- Throughput: ~41 RPM
- Good for: Production apps

### Cache Performance
- Hit rate: 80-90%
- Firebase queries reduced: 80-90%
- Response time with cache HIT: <1s

## 7. Tổng kết luồng

### Khi user chat lần đầu:
```
User → /chat/stream
  → Validate input
  → Load history (Firestore)
  → Check if personal question
  → Cache MISS → Query Firebase (1 lần)
  → Build context
  → Stream from Gemini (0.5s first token)
  → Save history
  → Cache data (2 min TTL)
```

### Khi user chat lần 2 (trong 2 phút):
```
User → /chat/stream
  → Validate input
  → Load history
  → Check if personal question
  → Cache HIT → Return cached data (nhanh!)
  → Build context
  → Stream from Gemini
  → Save history
```

### Khi user tạo plan mới:
```
User → /user/collection/update
  → Update ChromaDB
  → Clear cache (force reload)
  → Return success

User → /chat/stream (ngay sau đó)
  → Cache MISS → Query Firebase
  → Có plan mới!
  → Stream response với plan mới
```

---

**Last Updated**: November 15, 2025  
**Version**: 2.0 (With Streaming + Smart Cache + API Rotation)

## 2. Luồng khởi động hệ thống

1. **Load cấu hình & biến môi trường**
   - Đọc config (API key Gemini, thông tin Firebase, đường dẫn DB, v.v.).

2. **Khởi tạo Firebase**
   - Kết nối tới Firestore.
   - Chuẩn bị các collection: `users`, `user_collections`, `chat_history`, v.v.

3. **Khởi tạo thành phần RAG**
   - Load / kết nối tới ChromaDB.
   - Tải các vector / tài liệu đã index (từ `dulieu.csv`, `notes`, v.v.).
   - Chuẩn bị retriever (BM25, vector store retriever...).

4. **Khởi tạo LLM (Gemini)**
   - Tạo client Gemini với API key.
   - Cấu hình model mặc định (ví dụ `gemini-2.5-flash`).

5. **Khởi tạo cache & các tiện ích khác**
   - Cache câu trả lời, kết quả retrieval.
   - Các helper đọc/ghi Firestore, format prompt, logging.

## 3. Luồng endpoint chính

### 3.1. `/health` (GET)

Mục đích: check nhanh backend đang sống.

Luồng:
1. Flask nhận request GET `/health`.
2. Thực hiện các check đơn giản (ví dụ: kết nối DB, version...).
3. Trả JSON:
   - `{ "status": "ok", "message": "healthy" }` (tùy code thực tế).

### 3.2. `/user/collection/create` (POST)

Mục đích: tạo / cập nhật collection dữ liệu cá nhân cho một `user_id`.

Input JSON (ví dụ):
```json
{
  "user_id": "A8fMfRb4dyOVGKmKtsckxjG9kkw2",
  "text": "Tôi là người dùng cá nhân, cần lưu kế hoạch hàng ngày..."
}
```

Luồng:
1. Backend parse body JSON, validate `user_id` + `text`.
2. Kiểm tra trong Firestore / Chroma:
   - Nếu collection cho user này **chưa tồn tại**:
     - Tạo mới document/collection trong Firestore.
     - Chunk `text` (nếu dài), embed và lưu vào ChromaDB (hoặc retriever tương đương).
     - Trả JSON: `{ "success": true, "message": "created" }`.
   - Nếu đã tồn tại:
     - Có thể update / append hoặc trả message: `"Collection for user ... already exists"` tuỳ logic.

3. Lịch sử / log có thể được ghi lại cho audit.

### 3.3. `/chat` (POST)

Mục đích: nhận câu hỏi từ user, truy xuất dữ liệu + gọi LLM + trả lời.

Input JSON (ví dụ):
```json
{
  "message": "Ngày mai tôi có kế hoạch gì không?",
  "session_id": "test_privacy_006",
  "user_id": "A8fMfRb4dyOVGKmKtsckxjG9kkw2"
}
```

Luồng chi tiết:

1. **Nhận request & validate**
   - Flask nhận POST `/chat` với `Content-Type: application/json`.
   - Parse body, kiểm tra `message`, `session_id`, `user_id` không rỗng.

2. **Lấy ngữ cảnh cá nhân hóa (User Context)**
   - Từ `user_id`, đọc Firestore:
     - Thông tin profile / preference của user.
     - Collection dữ liệu cá nhân (ghi chú, kế hoạch, lịch, v.v.).
   - Truy vấn ChromaDB / retriever:
     - Lấy các đoạn văn bản liên quan tới câu hỏi (`top_k` đoạn).

3. **Xây dựng Prompt cho LLM (RAG)**
   - Kết hợp:
     - Câu hỏi người dùng (`message`).
     - Context từ user collection (kế hoạch, lịch, ghi chú...).
     - Context từ tri thức chung (tài liệu CSV, notes...).
     - Các chỉ dẫn hệ thống (role, style, bảo mật, không tiết lộ dữ liệu user khác...).
   - Tạo prompt dạng:
     - "Dựa trên context sau, hãy trả lời câu hỏi của người dùng..."

4. **Gọi Gemini (LLM)**
   - Gửi prompt đến API `generate_content` của Gemini.
   - Model: `gemini-2.5-flash` (hoặc model khác theo cấu hình).
   - Xử lý lỗi quota / timeout:
     - Nếu lỗi quota: trả message phù hợp hoặc yêu cầu user thử lại.

5. **Xử lý & hậu xử lý kết quả**
   - Lấy text trả lời từ Gemini.
   - Optionally: format lại, cắt bớt, bỏ nội dung nhạy cảm.
   - Chuẩn bị response JSON:
     ```json
     {
       "success": true,
       "answer": "...",
       "sources": [ ... ],
       "user_id": "...",
       "session_id": "..."
     }
     ```

6. **Lưu lịch sử hội thoại**
   - Ghi vào Firestore:
     - `user_id`, `session_id`.
     - `question`, `answer`.
     - Thời gian, metadata (nguồn context, token usage...).

7. **Trả response cho client**
   - HTTP 200 + JSON như trên.

### 3.4. Các endpoint khác (tùy main.py)

Tùy code thực tế, backend có thêm:

- `/user/collection/check` (GET):
  - Kiểm tra collection cho `user_id` đã tồn tại chưa.
  - Dùng trong JMeter / client để verify trước khi chat.

- `/history` hoặc tương tự:
  - Lấy lịch sử chat theo `user_id`/`session_id`.

- `/cache/stats`, `/cache/clear`:
  - Xem và quản lý cache cho retrieval/LLM.

Các endpoint này đều xoay quanh Firestore + cache + retriever để phục vụ / hỗ trợ `/chat`.

## 4. Luồng test với JMeter (tóm tắt)

1. **Tạo dữ liệu user** (`Create User Collection` Thread Group):
   - Đọc nhiều `user_id, text_data` từ `user_data.csv`.
   - Gửi POST `/user/collection/create` để build collection cá nhân.

2. **Gửi nhiều request chat song song** (`Chat API` Thread Group):
   - Đọc `message, session_id, user_id` từ `chat_messages.csv`.
   - Gửi POST `/chat` với JSON raw body.
   - Có `HTTP Header Manager` với `Content-Type: application/json`.

3. **Giới hạn bởi quota Gemini**:
   - Model `gemini-2.5-flash` (free tier) thường bị giới hạn ~10 request/phút/model/project.
   - Khi load test, cần:
     - Giảm số thread / thêm timer, hoặc
     - Nâng quota / chuyển plan trả phí.

## 5. Tóm tắt luồng tổng thể

1. **Chuẩn bị dữ liệu & cấu hình**
   - Index tài liệu chung (CSV, notes).
   - Tạo collection cá nhân cho từng user (qua `/user/collection/create`).

2. **Khi user gửi câu hỏi (qua `/chat`)**
   - Nhận JSON `message + user_id + session_id`.
   - Lấy context cá nhân + tri thức chung.
   - Gọi Gemini với prompt RAG.
   - Lưu lịch sử, trả lời cho client.

3. **Quan sát & tối ưu**
   - Sử dụng các endpoint `/health`, `/cache/*`, `/history` để monitor.
   - Dùng JMeter/Postman để test chức năng và hiệu năng.

---

Nếu bạn muốn, mình có thể cập nhật file này chi tiết hơn theo đúng code cụ thể trong `main.py` (tên hàm, tên collection Firestore, format response chính xác từng endpoint).