# Luồng hoạt động Chatbot Backend

Tài liệu này mô tả luồng hoạt động end-to-end của backend RAG Chatbot dùng Flask + Firebase + Gemini + Chroma.

## 1. Các thành phần chính

- **Flask API (`main.py`)**: điểm vào HTTP, định nghĩa các endpoint như `/health`, `/chat`, `/user/collection/*`, `/history`, `/cache/*`.
- **Firebase (Firestore/Auth)**: lưu user, collection dữ liệu cá nhân, lịch sử hội thoại, cấu hình hệ thống.
- **Gemini (Generative Language API)**: model ngôn ngữ chính (ví dụ `gemini-2.5-flash`) để sinh câu trả lời.
- **ChromaDB / BM25 / tài liệu CSV**: nguồn tri thức cho phần Retrieval (RAG), bao gồm kiến thức chung và dữ liệu cá nhân hóa theo user.

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