# 🚀 Hướng dẫn sử dụng Streaming API

## Tại sao nên dùng Streaming?

### Non-Streaming (Cũ)
```
User hỏi → Chờ 3-4 giây → Nhận toàn bộ response
❌ User phải chờ lâu
❌ Trải nghiệm kém
```

### Streaming (Mới) ✨
```
User hỏi → 0.5s → Bắt đầu thấy text → Text xuất hiện dần
✅ Response ngay lập tức
✅ Trải nghiệm như ChatGPT
✅ Tăng tốc độ cảm nhận 5-6 lần
```

---

## API Endpoints

### 1. Non-Streaming (Cũ)
```
POST /chat
```

### 2. Streaming (Mới - KHUYẾN NGHỊ)
```
POST /chat/stream
```

---

## Cách tích hợp vào Frontend

### Option 1: JavaScript/React (Web)

```javascript
async function chatWithStreaming(message, userId, sessionId) {
  const response = await fetch('https://your-api.com/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: message,
      user_id: userId,
      session_id: sessionId
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let fullAnswer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.substring(6);
        
        if (data === '[DONE]') {
          console.log('✅ Stream complete');
          continue;
        }

        try {
          const json = JSON.parse(data);
          
          if (json.type === 'start') {
            console.log('🚀 Stream started');
          } else if (json.type === 'token' && json.content) {
            // Hiển thị từng token ngay lập tức
            fullAnswer += json.content;
            updateUI(fullAnswer); // Cập nhật UI với text mới
          } else if (json.type === 'done') {
            console.log('✅ Full answer:', json.full_answer);
          }
        } catch (e) {
          console.error('Parse error:', e);
        }
      }
    }
  }

  return fullAnswer;
}

// Sử dụng
chatWithStreaming('Gợi ý địa điểm du lịch Đà Nẵng', 'user123', 'session123');
```

### Option 2: React Native / Flutter

```javascript
// React Native với fetch API
async function streamingChat(message, userId) {
  try {
    const response = await fetch('https://your-api.com/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: message,
        user_id: userId,
        session_id: 'session_' + Date.now()
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    // Đọc response dần dần
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        console.log('Stream finished');
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Giữ lại dòng chưa hoàn chỉnh

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const jsonStr = line.substring(6).trim();
          if (jsonStr && jsonStr !== '[DONE]') {
            try {
              const data = JSON.parse(jsonStr);
              if (data.type === 'token') {
                // Cập nhật UI ngay lập tức
                setMessage(prev => prev + data.content);
              }
            } catch (e) {
              console.warn('Parse error:', e);
            }
          }
        }
      }
    }
  } catch (error) {
    console.error('Streaming error:', error);
  }
}
```

### Option 3: Flutter (Dart)

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

Future<void> chatWithStreaming(String message, String userId) async {
  final url = Uri.parse('https://your-api.com/chat/stream');
  
  final request = http.Request('POST', url);
  request.headers['Content-Type'] = 'application/json';
  request.body = jsonEncode({
    'message': message,
    'user_id': userId,
    'session_id': 'session_${DateTime.now().millisecondsSinceEpoch}'
  });

  final response = await request.send();
  String fullAnswer = '';

  await for (var chunk in response.stream.transform(utf8.decoder)) {
    final lines = chunk.split('\n');
    
    for (var line in lines) {
      if (line.startsWith('data: ')) {
        final data = line.substring(6);
        
        if (data == '[DONE]') continue;
        
        try {
          final json = jsonDecode(data);
          
          if (json['type'] == 'token' && json['content'] != null) {
            fullAnswer += json['content'];
            // Cập nhật UI
            onNewToken(json['content']);
          }
        } catch (e) {
          print('Parse error: $e');
        }
      }
    }
  }
}
```

---

## Response Format

### Server-Sent Events (SSE)

```
data: {"type": "start", "session_id": "session123"}

data: {"type": "token", "content": "Đà"}

data: {"type": "token", "content": " Nẵng"}

data: {"type": "token", "content": " là"}

...

data: {"type": "done", "full_answer": "Đà Nẵng là một thành phố..."}

data: [DONE]
```

---

## Test với HTML (Demo)

Mở file `test_streaming.html` trong browser để test:

```html
<!DOCTYPE html>
<html>
<body>
  <textarea id="question" rows="3">Gợi ý 5 địa điểm du lịch ở Đà Nẵng</textarea>
  <button onclick="testStreaming()">Test Streaming</button>
  <div id="response"></div>

  <script>
    async function testStreaming() {
      const question = document.getElementById('question').value;
      const responseDiv = document.getElementById('response');
      responseDiv.textContent = '';

      const response = await fetch('http://localhost:8080/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: question,
          session_id: 'test_streaming'
        })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.substring(6);
            if (data === '[DONE]') continue;

            try {
              const json = JSON.parse(data);
              if (json.token) {
                responseDiv.textContent += json.token;
              }
            } catch (e) {
              // Skip invalid JSON
            }
          }
        }
      }
    }
  </script>
</body>
</html>
```

---

## So sánh Performance

| Metric | Non-Streaming | Streaming |
|--------|---------------|-----------|
| Time to First Byte (TTFB) | 2-3s | ~0.5s |
| Total Time | 3-4s | 3-4s |
| User Experience | ❌ Chờ lâu | ✅ Ngay lập tức |
| Best For | Simple apps | Production apps |

---

## Deploy lên Production

Khi deploy lên Cloud Run, đảm bảo:

1. **Timeout đủ lớn**: `--timeout=120`
2. **Memory đủ**: `--memory=512Mi` hoặc `1Gi`
3. **Instance concurrency**: `--concurrency=80`

```bash
gcloud run deploy rag-chatbot \
  --image gcr.io/your-project/rag-chatbot:latest \
  --platform managed \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --timeout=120 \
  --memory=1Gi \
  --concurrency=80 \
  --set-env-vars "GOOGLE_API_KEY_1=...,GOOGLE_API_KEY_2=...,GOOGLE_API_KEY_3=..."
```

---

## Monitoring

Xem stats của API keys:
```bash
curl https://your-api.com/api-stats
```

Xem cache stats:
```bash
curl https://your-api.com/cache/stats
```

---

## Troubleshooting

### 1. Không nhận được token
- Kiểm tra CORS headers
- Kiểm tra network tab trong browser
- Đảm bảo server đã bật streaming

### 2. Response bị delay
- Kiểm tra API key có bị quota limit không: `/api-stats`
- Thêm nhiều API keys để tăng throughput
- Kiểm tra cache có hoạt động không: `/cache/stats`

### 3. Cache không update
- Call `/cache/clear` với user_id sau khi update data
- Hoặc đợi 2 phút để cache tự hết hạn

---

## Best Practices

1. ✅ **Luôn dùng streaming** cho production
2. ✅ **Dùng 3 API keys** để tránh quota limit
3. ✅ **Set timeout phù hợp** trên client (30-60s)
4. ✅ **Handle errors gracefully** khi stream bị disconnect
5. ✅ **Clear cache** sau khi user update data

---

## Support

Nếu có vấn đề, kiểm tra:
- Server logs: `python main.py`
- API stats: `GET /api-stats`
- Cache stats: `GET /cache/stats`
- Test file: `test_streaming.html`
