"""
Script đánh giá độ chính xác của Chatbot RAG
Đọc câu hỏi từ hanoi_testdata.csv, gọi API chatbot, so sánh với câu trả lời mẫu
"""

import csv
import requests
import json
import time
from datetime import datetime
import os

# === CẤU HÌNH ===
TEST_DATA_FILE = "hanoi_testdata.csv"
API_ENDPOINT = "http://localhost:8080/chat"  # Thay bằng URL production nếu cần
RESULT_FILE = f"evaluation_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
DELAY_BETWEEN_REQUESTS = 1  # giây (để tránh rate limit)

# Session ID để tách biệt test với chat thật
TEST_SESSION_ID = "evaluation_test_session"

def load_test_data(file_path):
    """Đọc test data từ CSV"""
    test_cases = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                test_cases.append({
                    'id': row['ID'],
                    'question': row['Question'],
                    'ideal_answer': row['Ideal_Answer']
                })
        print(f"✅ Đã load {len(test_cases)} test cases từ {file_path}")
        return test_cases
    except Exception as e:
        print(f"❌ Lỗi khi đọc file {file_path}: {e}")
        return []

def call_chatbot_api(question, session_id=TEST_SESSION_ID):
    """Gọi API chatbot và lấy câu trả lời"""
    try:
        payload = {
            "message": question,
            "session_id": session_id
        }
        
        response = requests.post(
            API_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return {
                    'success': True,
                    'answer': data.get('answer', ''),
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'answer': '',
                    'error': data.get('error', 'Unknown error')
                }
        else:
            return {
                'success': False,
                'answer': '',
                'error': f"HTTP {response.status_code}: {response.text}"
            }
    
    except Exception as e:
        return {
            'success': False,
            'answer': '',
            'error': str(e)
        }

def save_results(results, output_file):
    """Lưu kết quả vào CSV"""
    try:
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            fieldnames = [
                'ID',
                'Question',
                'Ideal_Answer',
                'Chatbot_Answer',
                'Status',
                'Result',
                'Notes'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                writer.writerow({
                    'ID': result['id'],
                    'Question': result['question'],
                    'Ideal_Answer': result['ideal_answer'],
                    'Chatbot_Answer': result['chatbot_answer'],
                    'Status': result['status'],
                    'Result': '',  # Để người dùng tự đánh giá (Đạt/Không Đạt)
                    'Notes': result.get('error', '')
                })
        
        print(f"\n✅ Đã lưu kết quả vào: {output_file}")
        return True
    
    except Exception as e:
        print(f"❌ Lỗi khi lưu file: {e}")
        return False

def run_evaluation():
    """Chạy quá trình đánh giá"""
    print("="*80)
    print("  ĐÁNH GIÁ ĐỘ CHÍNH XÁC CHATBOT RAG")
    print("="*80)
    print(f"API Endpoint: {API_ENDPOINT}")
    print(f"Test Data: {TEST_DATA_FILE}")
    print(f"Session ID: {TEST_SESSION_ID}")
    print(f"Delay: {DELAY_BETWEEN_REQUESTS}s giữa các requests")
    print("="*80)
    
    # 1. Load test data
    test_cases = load_test_data(TEST_DATA_FILE)
    if not test_cases:
        print("❌ Không có test cases để chạy!")
        return
    
    # 2. Kiểm tra API có hoạt động không
    print(f"\n🔍 Kiểm tra API endpoint...")
    try:
        health_response = requests.get(API_ENDPOINT.replace('/chat', '/health'), timeout=5)
        if health_response.status_code == 200:
            print("✅ API đang hoạt động")
        else:
            print(f"⚠️ API trả về status code: {health_response.status_code}")
    except Exception as e:
        print(f"❌ Không thể kết nối đến API: {e}")
        print("   Hãy đảm bảo server đang chạy!")
        return
    
    # 3. Chạy từng test case
    results = []
    total = len(test_cases)
    
    print(f"\n🚀 Bắt đầu test {total} câu hỏi...\n")
    
    for idx, test_case in enumerate(test_cases, 1):
        test_id = test_case['id']
        question = test_case['question']
        ideal_answer = test_case['ideal_answer']
        
        print(f"[{idx}/{total}] {test_id}: {question}")
        
        # Gọi API
        api_result = call_chatbot_api(question)
        
        if api_result['success']:
            chatbot_answer = api_result['answer']
            status = "SUCCESS"
            print(f"  ✅ Chatbot: {chatbot_answer[:100]}...")
        else:
            chatbot_answer = ""
            status = "ERROR"
            print(f"  ❌ Lỗi: {api_result['error']}")
        
        # Lưu kết quả
        results.append({
            'id': test_id,
            'question': question,
            'ideal_answer': ideal_answer,
            'chatbot_answer': chatbot_answer,
            'status': status,
            'error': api_result.get('error', '')
        })
        
        # Delay để tránh rate limit
        if idx < total:
            time.sleep(DELAY_BETWEEN_REQUESTS)
    
    # 4. Lưu kết quả
    print("\n" + "="*80)
    print("  KẾT QUẢ ĐÁNH GIÁ")
    print("="*80)
    
    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    error_count = sum(1 for r in results if r['status'] == 'ERROR')
    
    print(f"Tổng số test cases: {total}")
    print(f"Thành công: {success_count} ({success_count/total*100:.1f}%)")
    print(f"Lỗi: {error_count} ({error_count/total*100:.1f}%)")
    
    # 5. Lưu file CSV
    if save_results(results, RESULT_FILE):
        print(f"\n📊 Mở file '{RESULT_FILE}' để đánh giá thủ công:")
        print("   - Cột 'Result': Điền 'Đạt' hoặc 'Không Đạt'")
        print("   - Cột 'Notes': Ghi chú lý do (nếu Không Đạt)")
        print("\n✨ Tiêu chí đánh giá:")
        print("   ✅ Đạt: Trả lời đúng, bám sát kiến thức, không bịa đặt")
        print("   ❌ Không Đạt: Hallucination, Retrieval Failure, hoặc Irrelevant")
    
    print("="*80)

if __name__ == "__main__":
    # Clear history trước khi test (tránh ảnh hưởng từ chat cũ)
    try:
        print("\n🗑️ Xóa lịch sử chat test session...")
        requests.post(
            API_ENDPOINT.replace('/chat', '/history/clear'),
            json={"session_id": TEST_SESSION_ID},
            timeout=5
        )
        print("✅ Đã xóa lịch sử\n")
    except:
        print("⚠️ Không thể xóa lịch sử (có thể endpoint chưa có)\n")
    
    # Chạy evaluation
    run_evaluation()
