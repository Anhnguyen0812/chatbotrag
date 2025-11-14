# File: chatbot_rag_bm25.py (Phiên bản TẢI DỮ LIỆU SẴN)

import os
import pickle
from dotenv import load_dotenv

# Import các thư viện
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.document_loaders import CSVLoader # Vẫn cần để import Document
from langchain.retrievers import BM25Retriever
from langchain.prompts import PromptTemplate
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

# --- Cấu hình ---
DOCUMENTS_PICKLE_FILE = "bm25_documents.pkl"

# --- 1. Tải API Key ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("Google API Key không được tìm thấy. Vui lòng thiết lập trong file .env.")

# --- 2. TẢI Documents đã lưu trữ và Tạo BM25 Retriever ---
if not os.path.exists(DOCUMENTS_PICKLE_FILE):
    raise FileNotFoundError(f"Không tìm thấy file Documents tại '{DOCUMENTS_PICKLE_FILE}'. Vui lòng chạy prepare_bm25_data.py trước!")

print(f"Đang tải Documents từ file '{DOCUMENTS_PICKLE_FILE}'...")

# Tải danh sách Documents từ file pickle
with open(DOCUMENTS_PICKLE_FILE, 'rb') as f:
    documents = pickle.load(f)

print(f"-> Đã tải {len(documents)} documents thành công.")

# Tạo BM25 Retriever ngay lập tức từ danh sách documents trong bộ nhớ
print("Đang tạo BM25 retriever...")
retriever = BM25Retriever.from_documents(
    documents,
    k=3 # Lấy top 3 kết quả liên quan nhất
)
print("BM25 retriever đã sẵn sàng.")

# --- 3. Khởi tạo mô hình Gemini Flash (giữ nguyên) ---
llm = ChatGoogleGenerativeAI(
    model="gemini-flash-latest",
    google_api_key=GOOGLE_API_KEY,
    temperature=0.5,
    convert_system_message_to_human=True
)

# --- 4. Tạo Prompt Template và RAG Chain (giữ nguyên) ---
prompt_template = """
Bạn là một trợ lý AI hữu ích, chuyên gia về gợi ý du lịch và quà tặng.
Nhiệm vụ của bạn là trả lời câu hỏi của người dùng một cách thân thiện, chi tiết và chỉ dựa trên thông tin được cung cấp trong phần ngữ cảnh dưới đây.
Nếu thông tin không có trong ngữ cảnh, hãy nói rằng bạn không tìm thấy thông tin phù hợp trong dữ liệu của mình. Tuyệt đối không bịa đặt thông tin.

NGỮ CẢNH:
{context}

CÂU HỎI: {input}

CÂU TRẢ LỜI (viết bằng tiếng Việt):
"""

prompt = PromptTemplate.from_template(prompt_template)
document_chain = create_stuff_documents_chain(llm, prompt)
retrieval_chain = create_retrieval_chain(retriever, document_chain)

# --- 5. Tạo vòng lặp Chatbot (giữ nguyên) ---
def chat():
    print("\n--- Chatbot Gợi Ý (BM25 + Gemini - Tải nhanh) ---")
    print("Nhập 'thoat' để kết thúc.")
    while True:
        user_input = input("\nBạn: ")
        if user_input.lower() == 'thoat':
            print("Chatbot: Tạm biệt!")
            break
        if user_input:
            print("Bot đang tìm kiếm và suy nghĩ...")
            response = retrieval_chain.invoke({"input": user_input})
            print("\nBot:", response["answer"])

if __name__ == "__main__":
    chat()