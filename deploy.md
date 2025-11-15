Bước 1: Build Docker Image mới (với --no-cache)

gcloud builds submit --tag gcr.io/couples-app-b83be/rag-chatbot:latest --no-cache

Lưu ý: Dùng --no-cache để đảm bảo build hoàn toàn từ đầu với code mới nhất.

Bước 2: Deploy lên Cloud Run

# Cách 1: Deploy với 3 API keys (Rotation System - KHUYẾN NGHỊ)
gcloud run deploy rag-chatbot `
  --image gcr.io/couples-app-b83be/rag-chatbot:latest `
  --platform managed `
  --region asia-southeast1 `
  --allow-unauthenticated `
  --set-env-vars "FIREBASE_STORAGE_BUCKET=couples-app-b83be.firebasestorage.app,GOOGLE_API_KEY_1=AIzaSyDiYeNt2-7LWhj6GAMK4Aj2Ae3f1spCrOM,GOOGLE_API_KEY_2=AIzaSyBX88f9VrYSsFeZOmm_naPT2Mz2eiBJGzU,GOOGLE_API_KEY_3=AIzaSyAdhKnPgPXomYWMU236j7YvfS092lhCPro,
  GOOGLE_API_KEY_4=AIzaSyDoAwrWJ-q01UsRpcGYaRtI-fjKSdOVZBc,
  GOOGLE_API_KEY_5=AIzaSyBqD8Uy1sGSx_HguT5GpTK61J9mhMj_toE,
  GOOGLE_API_KEY_6=AIzaSyDK8yve1s9TUfRsmKEjyj-KAB5Qs5VfftI"

# Cách 2: Deploy với 1 API key (Backward compatible - Cũ)
gcloud run deploy rag-chatbot `
  --image gcr.io/couples-app-b83be/rag-chatbot:latest `
  --platform managed `
  --region asia-southeast1 `
  --allow-unauthenticated `
  --set-env-vars "FIREBASE_STORAGE_BUCKET=couples-app-b83be.firebasestorage.app,GOOGLE_API_KEY=AIzaSyCqz87u94WzdVTGH3prTt4WsDrnSFbzgQw"

# LƯU Ý: Thay YOUR_KEY_1_HERE, YOUR_KEY_2_HERE, YOUR_KEY_3_HERE bằng các API keys thật của bạn

Bước 3: Chuyển traffic sang revision mới nhất

gcloud run services update-traffic rag-chatbot --to-revisions LATEST=100 --region asia-southeast1
