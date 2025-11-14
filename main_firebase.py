# Backend Chatbot API cho Firebase Functions
# Version: Firebase Functions compatible

import os
import pickle
from typing import Dict, List
from datetime import datetime

# Firebase Functions imports
from firebase_functions import https_fn, options
from firebase_admin import initialize_app, firestore
import google.cloud.firestore

# Flask imports
from flask import Flask, request, jsonify
from flask_cors import CORS

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.retrievers import BM25Retriever
from langchain.prompts import PromptTemplate
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

# Initialize Firebase Admin
initialize_app()

# --- Cấu hình ---
DOCUMENTS_PICKLE_FILE = "bm25_documents.pkl"
MAX_HISTORY_SIZE = 5

# Khởi tạo Flask app
app = Flask(__name__)
CORS(app)

# Firestore client (for production history storage)
db = firestore.client()

# --- Helper: Lấy API Key ---
def get_google_api_key():
    """Lấy Google API Key từ environment hoặc Firebase config"""
    # Try environment variable first (for local dev)
    api_key = os.getenv("GOOGLE_API_KEY")
    
    # For Firebase Functions, use functions config
    if not api_key:
        # firebase functions:config:set google.api_key="YOUR_KEY"
        api_key = os.environ.get("GOOGLE_API_KEY")
    
    if not api_key:
        raise ValueError("Google API Key không được tìm thấy")
    
    return api_key

# --- Khởi tạo Chatbot ---
def initialize_chatbot():
    """Khởi tạo BM25 Retriever và LLM"""
    if not os.path.exists(DOCUMENTS_PICKLE_FILE):
        raise FileNotFoundError(f"Không tìm thấy file {DOCUMENTS_PICKLE_FILE}")
    
    print(f"Loading documents from {DOCUMENTS_PICKLE_FILE}...")
    with open(DOCUMENTS_PICKLE_FILE, 'rb') as f:
        documents = pickle.load(f)
    print(f"Loaded {len(documents)} documents")
    
    # BM25 Retriever
    retriever = BM25Retriever.from_documents(documents, k=3)
    
    # Gemini LLM
    api_key = get_google_api_key()
    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        google_api_key=api_key,
        temperature=0.7,
        convert_system_message_to_human=True
    )
    
    # Prompt với lịch sử
    prompt_template = """
Bạn là một trợ lý AI hữu ích, chuyên gia về gợi ý du lịch và quà tặng.

LƯU Ý QUAN TRỌNG: KHÔNG ĐƯỢC TẠO BẢNG trong câu trả lời. KHÔNG SỬ DỤNG BẢNG Markdown hay các định dạng bảng nào.
Nếu thông tin cần được trình bày theo dạng bảng, hãy chuyển sang danh sách gạch đầu dòng hoặc danh sách đánh số với các nhãn rõ ràng.

LỊCH SỬ HỘI THOẠI GẦN ĐÂY:
{history}

NGỮ CẢNH TỪ CƠ SỞ DỮ LIỆU:
{context}

CÂU HỎI: {input}

Hãy trả lời bằng tiếng Việt, thân thiện và chi tiết. Chỉ dựa trên thông tin trong ngữ cảnh.

CÂU TRẢ LỜI:
"""
    
    prompt = PromptTemplate.from_template(prompt_template)
    document_chain = create_stuff_documents_chain(llm, prompt)
    retrieval_chain = create_retrieval_chain(retriever, document_chain)
    
    return retrieval_chain

# Global retrieval chain (lazy initialization)
retrieval_chain = None

def get_retrieval_chain():
    """Lazy load retrieval chain"""
    global retrieval_chain
    if retrieval_chain is None:
        print("=== INITIALIZING CHATBOT ===")
        retrieval_chain = initialize_chatbot()
        print("=== CHATBOT READY ===")
    return retrieval_chain

# --- Firestore History Management ---
def get_history_from_firestore(session_id: str) -> List[Dict]:
    """Lấy lịch sử từ Firestore"""
    try:
        doc_ref = db.collection('chat_sessions').document(session_id)
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            return data.get('history', [])
        return []
    except Exception as e:
        print(f"Error getting history: {e}")
        return []

def save_history_to_firestore(session_id: str, history: List[Dict]):
    """Lưu lịch sử vào Firestore"""
    try:
        doc_ref = db.collection('chat_sessions').document(session_id)
        doc_ref.set({
            'history': history,
            'updated_at': datetime.now()
        })
    except Exception as e:
        print(f"Error saving history: {e}")

def get_history_text(session_id: str) -> str:
    """Lấy lịch sử dưới dạng text"""
    history = get_history_from_firestore(session_id)
    
    if not history:
        return "Chưa có lịch sử hội thoại."
    
    history_text = []
    for item in history:
        history_text.append(f"Người dùng: {item['question']}")
        history_text.append(f"Bot: {item['answer']}")
    
    return "\n".join(history_text)

def add_to_history(session_id: str, question: str, answer: str):
    """Thêm vào lịch sử"""
    history = get_history_from_firestore(session_id)
    
    history.append({
        "question": question,
        "answer": answer,
        "timestamp": datetime.now().isoformat()
    })
    
    # Giữ chỉ 5 câu gần nhất
    if len(history) > MAX_HISTORY_SIZE:
        history = history[-MAX_HISTORY_SIZE:]
    
    save_history_to_firestore(session_id, history)

def clear_history(session_id: str):
    """Xóa lịch sử"""
    save_history_to_firestore(session_id, [])

# --- API Routes ---
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "message": "Chatbot backend is running",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({"error": "Missing 'message'"}), 400
        
        session_id = data.get('session_id', 'default')
        user_message = data['message'].strip()
        
        if not user_message:
            return jsonify({"error": "Message cannot be empty"}), 400
        
        # Lấy lịch sử
        history_text = get_history_text(session_id)
        
        # Gọi RAG chain (lazy load)
        chain = get_retrieval_chain()
        response = chain.invoke({
            "input": user_message,
            "history": history_text
        })
        
        bot_answer = response["answer"]
        
        # Lưu lịch sử
        add_to_history(session_id, user_message, bot_answer)
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "question": user_message,
            "answer": bot_answer,
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/history', methods=['GET'])
def get_history():
    try:
        session_id = request.args.get('session_id', 'default')
        history = get_history_from_firestore(session_id)
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "history": history,
            "count": len(history)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/history/clear', methods=['POST'])
def clear_chat_history():
    try:
        data = request.get_json()
        session_id = data.get('session_id', 'default')
        
        clear_history(session_id)
        
        return jsonify({
            "success": True,
            "message": "History cleared",
            "session_id": session_id
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- Firebase Functions Entry Point ---
@https_fn.on_request(
    cors=options.CorsOptions(
        cors_origins="*",
        cors_methods=["get", "post"],
    ),
    memory=options.MemoryOption.MB_512,
    timeout_sec=120
)
def api(req: https_fn.Request) -> https_fn.Response:
    """Firebase Functions entry point"""
    with app.request_context(req.environ):
        return app.full_dispatch_request()

# --- Local Development ---
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
