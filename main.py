# Backend Chatbot API cho Firebase Functions
# Version: Firebase Functions compatible

import os
import pickle
from typing import Dict, List
from datetime import datetime
import pytz

# Load environment variables first (for local development)
from dotenv import load_dotenv
load_dotenv()

# Firebase Functions imports
from firebase_functions import https_fn, options
from firebase_admin import initialize_app, firestore
import google.cloud.firestore

# Flask imports
from flask import Flask, request, jsonify
from flask_cors import CORS

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.retrievers import BM25Retriever
from langchain.prompts import PromptTemplate
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

# User personalization imports
from manageDataFirebase.buildCollectionUser import build_collection_user
from manageDataFirebase.buildDataApp import build_data_app
from manageDataFirebase.getUserCollection import get_user_collection
from manageDataFirebase.updateCollectionExists import update_collection_exists
from manageDataFirebase.deleteDataColletionExists import delete_data_collection_exists
from manageDataFirebase.checkCollectionExists import check_collection_exists

# Initialize Firebase Admin (only if not already initialized by firebaseClient)
try:
    from firebase_admin import get_app
    try:
        get_app()
        print("✅ Firebase đã được khởi tạo bởi firebaseClient")
    except ValueError:
        initialize_app()
        print("✅ Firebase được khởi tạo trong main.py")
except Exception as e:
    print(f"⚠️ Cảnh báo Firebase initialization: {e}")

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


def get_current_time_info() -> Dict[str, str]:
    """Return current time information in UTC and Vietnam timezone.

    Returns a dict with keys: utc_iso, vn_iso, vn_human
    """
    # Use timezone-aware datetime (Python 3.11+)
    utc_now = datetime.now(pytz.utc)
    try:
        tz_vn = pytz.timezone('Asia/Ho_Chi_Minh')
    except Exception:
        tz_vn = pytz.FixedOffset(7 * 60)

    vn_now = utc_now.astimezone(tz_vn)

    return {
        'utc_iso': utc_now.isoformat(),
        'vn_iso': vn_now.isoformat(),
        'vn_human': vn_now.strftime('%Y-%m-%d %H:%M:%S %Z')
    }

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
        temperature=0.5,
        convert_system_message_to_human=True
    )
    
    # Prompt với lịch sử
    # NOTE: We add a strict instruction to avoid producing tables (especially Markdown tables)
    # This is important for clients or integrations that cannot render tables.
    prompt_template = """
Bạn là một trợ lý AI hữu ích, chuyên gia về gợi ý du lịch và quà tặng.

THỜI GIAN HIỆN TẠI (QUAN TRỌNG - SỬ DỤNG ĐỂ TÍNH TOÁN):
- Múi giờ Việt Nam: {current_time}
- Hãy sử dụng thông tin này để xác định "hôm nay", "ngày mai", "hôm qua" khi người dùng hỏi về kế hoạch hoặc thời gian.
- Ví dụ: Nếu hôm nay là 2025-11-02, thì "ngày mai" là 2025-11-03, "hôm qua" là 2025-11-01.

PHẠM VI TRÁCH NHIỆM (QUAN TRỌNG):
- Bạn CHỈ được trả lời các câu hỏi về: du lịch Việt Nam, địa điểm tham quan, gợi ý quà tặng, lịch trình du lịch, thông tin người yêu/kế hoạch cá nhân (nếu có).
- Bạn CÓ THỂ trả lời về thời gian hiện tại (hôm nay, ngày mai, giờ) khi người dùng hỏi.
- Nếu câu hỏi KHÔNG thuộc các chủ đề trên (ví dụ: toán học, lịch sử thế giới, khoa học, công nghệ, nấu ăn, thể thao, v.v.), hãy TỪ CHỐI lịch sự bằng câu:
  
  "Xin lỗi, tôi chỉ có thể hỗ trợ về gợi ý du lịch và quà tặng. Tôi không thể trả lời câu hỏi về [chủ đề]."

LƯU Ý QUAN TRỌNG: 
1. KHÔNG ĐƯỢC TẠO BẢNG trong câu trả lời. KHÔNG SỬ DỤNG BẢNG Markdown hay các định dạng bảng nào.
   Nếu thông tin cần được trình bày theo dạng bảng, hãy chuyển sang danh sách gạch đầu dòng hoặc danh sách đánh số với các nhãn rõ ràng.

2. CHỈ SỬ DỤNG THÔNG TIN CÁ NHÂN KHI ĐƯỢC HỎI TRỰC TIẾP:
   - Nếu người dùng KHÔNG hỏi về thông tin cá nhân, người yêu, hoặc kế hoạch của họ, thì ĐỪNG ĐỀ CẬP đến những thông tin đó.
   - Chỉ trả lời về chủ đề mà người dùng đang hỏi (ví dụ: du lịch chung, quà tặng chung).
   - Nếu có "THÔNG TIN CÁ NHÂN CỦA NGƯỜI DÙNG" trong lịch sử, nghĩa là người dùng ĐÃ HỎI về thông tin cá nhân, lúc đó mới sử dụng.

3. TÍNH TOÁN THỜI GIAN CHÍNH XÁC:
   - Khi người dùng hỏi về "ngày mai", "hôm qua", "tuần sau", hãy tính toán dựa trên THỜI GIAN HIỆN TẠI ở trên.
   - Trả lời rõ ràng ngày tháng cụ thể, không chỉ nói "bạn có thể đối chiếu".

LỊCH SỬ HỘI THOẠI GẦN ĐÂY:
{history}

NGỮ CẢNH TỪ CƠ SỞ DỮ LIỆU (CHỈ VỀ DU LỊCH & QUÀ TẶNG & THÔNG TIN CÁ NHÂN):
{context}

CÂU HỎI: {input}

HƯỚNG DẪN TRẢ LỜI:
- Nếu câu hỏi về du lịch/quà tặng/thời gian: Trả lời chi tiết, thân thiện bằng tiếng Việt.
- Nếu câu hỏi về kế hoạch theo thời gian: Sử dụng THỜI GIAN HIỆN TẠI để tính toán chính xác.
- Nếu câu hỏi NGOÀI phạm vi (toán học, khoa học, v.v.): TỪ CHỐI lịch sự như hướng dẫn phía trên.
- Nhớ: ĐỪNG tự động đề cập thông tin cá nhân nếu người dùng không hỏi về nó.

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
@app.route('/', methods=['GET'])
def root():
    """Root endpoint - redirect to health check"""
    return jsonify({
        "status": "ok",
        "message": "RAG Chatbot API with Firebase Cache",
        "version": "2.1",
        "endpoints": {
            "health": "/health",
            "chat": "/chat (POST)",
            "history": "/history (GET)",
            "user_create": "/user/collection/create (POST)",
            "user_check": "/user/collection/check (GET)",
            "user_update": "/user/collection/update (POST)",
            "user_delete": "/user/collection/delete (DELETE)",
            "user_query": "/user/collection/query (POST)",
            "cache_stats": "/cache/stats (GET)",
            "cache_invalidate": "/cache/invalidate/<user_id> (POST)",
            "cache_clear": "/cache/clear (POST)"
        },
        "timestamp": datetime.now().isoformat()
    })

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "message": "Chatbot backend is running",
        "timestamp": datetime.now().isoformat()
    })

def is_personal_question(message: str) -> bool:
    """
    Kiểm tra xem câu hỏi có liên quan đến thông tin cá nhân không
    """
    message_lower = message.lower()
    
    # Từ khóa liên quan đến thông tin cá nhân
    personal_keywords = [
        # Thông tin người dùng
        'tôi', 'mình', 'em', 'của tôi', 'của mình', 'của em',
        'sinh nhật', 'ngày sinh', 'tuổi', 'bao nhiêu tuổi',
        'tên tôi', 'tên mình', 'tên em',
        
        # Thông tin người yêu
        'người yêu', 'bạn trai', 'bạn gái', 'ny', 'crush',
        'của anh ấy', 'của cô ấy', 'của bạn ấy',
        
        # Thông tin mối quan hệ
        'hẹn hò', 'yêu nhau', 'bắt đầu yêu', 'kỷ niệm',
        'chúng tôi', 'hai đứa', 'hai người', 'cả hai',
        
        # Thông tin kế hoạch
        'kế hoạch của tôi', 'kế hoạch của mình', 'kế hoạch của em',
        'kế hoạch chúng tôi', 'định làm gì', 'sắp đi đâu',
        'dự định', 'có kế hoạch nào'
    ]
    
    # Kiểm tra xem có từ khóa nào trong câu hỏi không
    for keyword in personal_keywords:
        if keyword in message_lower:
            return True
    
    return False

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({"error": "Missing 'message'"}), 400
        
        session_id = data.get('session_id', 'default')
        user_id = data.get('user_id')  # Optional: User ID for personalization
        user_message = data['message'].strip()
        
        if not user_message:
            return jsonify({"error": "Message cannot be empty"}), 400
        
        # Lấy lịch sử hội thoại
        history_text = get_history_text(session_id)
        
        # Kiểm tra xem câu hỏi có liên quan đến thông tin cá nhân không
        use_personal_context = is_personal_question(user_message)
        
        # Lấy thông tin cá nhân của user CHỈ KHI CẦN THIẾT
        personal_context = ""
        has_personal_context = False
        if user_id and use_personal_context:
            try:
                # Load dữ liệu REALTIME từ Firebase, không dùng cache/pickle
                from manageDataFirebase.buildDataApp import get_user_data_from_firebase
                user_docs = get_user_data_from_firebase(user_id)
                
                if user_docs:
                    personal_context = "\n\nTHÔNG TIN CÁ NHÂN CỦA NGƯỜI DÙNG:\n"
                    personal_context += "\n".join([f"- {doc}" for doc in user_docs])
                    has_personal_context = True
                    print(f"✅ Đã lấy {len(user_docs)} thông tin từ Firebase cho user {user_id}")
                else:
                    print(f"⚠️ User {user_id} chưa có dữ liệu trong Firebase")
            except Exception as e:
                print(f"⚠️ Lỗi khi lấy thông tin từ Firebase: {e}")
                import traceback
                traceback.print_exc()
        elif user_id and not use_personal_context:
            print(f"ℹ️ Câu hỏi không liên quan đến thông tin cá nhân, bỏ qua Firebase data cho user {user_id}")
        
        # Gọi RAG chain với context được mở rộng
        chain = get_retrieval_chain()

        # Kết hợp history với personal context
        enhanced_history = history_text
        if personal_context:
            enhanced_history = f"{history_text}\n{personal_context}"

        # Thêm thông tin thời gian hiện tại vào input để LLM có ngữ cảnh thời gian
        current_time = get_current_time_info()
        
        # Format current_time thành string để truyền vào prompt
        current_time_str = f"{current_time['vn_human']} (UTC: {current_time['utc_iso']})"

        response = chain.invoke({
            "input": user_message,
            "history": enhanced_history,
            "current_time": current_time_str
        })
        
        bot_answer = response["answer"]
        
        # Lưu lịch sử
        add_to_history(session_id, user_message, bot_answer)
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "user_id": user_id,
            "question": user_message,
            "answer": bot_answer,
            "has_personal_context": has_personal_context,
            "used_personal_data": use_personal_context,
            "timestamp": datetime.now().isoformat(),
            "current_time": current_time
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

# --- User Personalization API Routes ---

@app.route('/user/collection/create', methods=['POST'])
def create_user_collection():
    """Tạo collection ChromaDB cho user mới"""
    try:
        data = request.get_json()
        
        if not data or 'user_id' not in data:
            return jsonify({"error": "Missing 'user_id'"}), 400
        
        user_id = data['user_id']
        text = data.get('text', '')
        
        if not text:
            return jsonify({"error": "Missing 'text' data"}), 400
        
        # Kiểm tra collection đã tồn tại chưa
        if check_collection_exists(user_id):
            return jsonify({
                "success": False,
                "message": f"Collection for user {user_id} already exists"
            }), 400
        
        # Tạo collection mới
        build_collection_user(userID=user_id, text=text)
        
        return jsonify({
            "success": True,
            "message": f"Collection created for user {user_id}",
            "user_id": user_id
        })
    
    except Exception as e:
        print(f"Error creating user collection: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/user/collection/check', methods=['GET'])
def check_user_collection():
    """Kiểm tra collection của user có tồn tại không"""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({"error": "Missing 'user_id'"}), 400
        
        exists = check_collection_exists(user_id)
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "exists": exists
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/user/collection/update', methods=['POST'])
def update_user_collection():
    """Thêm/cập nhật text vào collection của user"""
    try:
        data = request.get_json()
        
        if not data or 'user_id' not in data or 'text' not in data or 'text_id' not in data:
            return jsonify({"error": "Missing required fields: user_id, text, text_id"}), 400
        
        user_id = data['user_id']
        text = data['text']
        text_id = data['text_id']
        
        # Kiểm tra collection tồn tại
        if not check_collection_exists(user_id):
            return jsonify({
                "success": False,
                "message": f"Collection for user {user_id} does not exist. Create it first."
            }), 404
        
        # Update collection
        update_collection_exists(userId=user_id, text=text, textId=text_id)
        
        return jsonify({
            "success": True,
            "message": f"Collection updated for user {user_id}",
            "user_id": user_id,
            "text_id": text_id
        })
    
    except Exception as e:
        print(f"Error updating user collection: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/user/collection/delete', methods=['POST'])
def delete_from_user_collection():
    """Xóa text khỏi collection của user"""
    try:
        data = request.get_json()
        
        if not data or 'user_id' not in data or 'text_id' not in data:
            return jsonify({"error": "Missing required fields: user_id, text_id"}), 400
        
        user_id = data['user_id']
        text_id = data['text_id']
        
        # Kiểm tra collection tồn tại
        if not check_collection_exists(user_id):
            return jsonify({
                "success": False,
                "message": f"Collection for user {user_id} does not exist"
            }), 404
        
        # Delete from collection
        delete_data_collection_exists(userId=user_id, textID=text_id)
        
        return jsonify({
            "success": True,
            "message": f"Data deleted from user {user_id} collection",
            "user_id": user_id,
            "text_id": text_id
        })
    
    except Exception as e:
        print(f"Error deleting from user collection: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/user/collection/query', methods=['POST'])
def query_user_collection():
    """Query user's personalized collection"""
    try:
        data = request.get_json()
        
        if not data or 'user_id' not in data or 'query' not in data:
            return jsonify({"error": "Missing required fields: user_id, query"}), 400
        
        user_id = data['user_id']
        query = data['query']
        k = data.get('k', 3)  # Number of results
        
        # Kiểm tra collection tồn tại
        if not check_collection_exists(user_id):
            return jsonify({
                "success": False,
                "message": f"Collection for user {user_id} does not exist"
            }), 404
        
        # Get collection and query
        collection = get_user_collection(user_id=user_id)
        results = collection.similarity_search(query, k=k)
        
        # Format results
        formatted_results = [
            {
                "content": doc.page_content,
                "metadata": doc.metadata
            }
            for doc in results
        ]
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "query": query,
            "results": formatted_results,
            "count": len(formatted_results)
        })
    
    except Exception as e:
        print(f"Error querying user collection: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/cache/stats', methods=['GET'])
def cache_stats():
    """Get cache statistics"""
    try:
        from firebaseCache import get_cache
        cache = get_cache()
        stats = cache.get_stats()
        
        return jsonify({
            "success": True,
            "cache_stats": stats,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/cache/invalidate/<user_id>', methods=['POST'])
def invalidate_user_cache(user_id):
    """Invalidate cache for specific user"""
    try:
        from firebaseCache import get_cache
        cache = get_cache()
        cache.invalidate(user_id)
        
        return jsonify({
            "success": True,
            "message": f"Cache invalidated for user {user_id}",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/cache/clear', methods=['POST'])
def clear_all_cache():
    """Clear all cache (Admin only)"""
    try:
        from firebaseCache import get_cache
        cache = get_cache()
        cache.clear()
        
        return jsonify({
            "success": True,
            "message": "All cache cleared",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/build-all-data', methods=['POST'])
def build_all_user_data():
    """Build toàn bộ dữ liệu từ Firebase vào ChromaDB (Admin only)"""
    try:
        # Optional: Add authentication check here
        auth_token = request.headers.get('Authorization')
        # if auth_token != "your-admin-token":
        #     return jsonify({"error": "Unauthorized"}), 401
        
        # Build all data
        build_data_app()
        
        return jsonify({
            "success": True,
            "message": "All user data has been built successfully"
        })
    
    except Exception as e:
        print(f"Error building all data: {e}")
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

# --- Firebase Realtime Sync ---
def build_initial_data():
    """Build dữ liệu ban đầu từ Firebase (nếu chưa có)"""
    try:
        from simpleUserData import get_stats
        
        # Kiểm tra xem đã có user data chưa
        stats = get_stats()
        
        if stats['total_users'] == 0:
            print("\n📦 Chưa có dữ liệu user")
            print("🔄 Đang build dữ liệu ban đầu từ Firebase...")
            
            # Build toàn bộ data
            build_data_app()
            
            # Check lại
            stats = get_stats()
            print(f"✅ Đã build data cho {stats['total_users']} users ({stats['total_documents']} documents)")
        else:
            print(f"\n✅ Đã có data cho {stats['total_users']} users ({stats['total_documents']} documents)")
            print("   Bỏ qua build initial data")
            
    except Exception as e:
        print(f"⚠️ Không thể build initial data: {e}")
        print("   Bạn có thể build thủ công: POST /admin/build-all-data")

def start_firebase_sync():
    """Khởi động realtime sync từ Firebase sang ChromaDB"""
    try:
        from manageDataFirebase.uploadData import (
            upload_data_users,
            upload_data_couples,
            upload_data_couplePlans
        )
        
        print("\n🔄 Đang khởi động Firebase Realtime Sync...")
        
        # Listener cho users collection
        users_ref = db.collection("users")
        users_watch = users_ref.on_snapshot(upload_data_users)
        print("   ✅ Listener 'users' đã khởi động")
        
        # Listener cho couples collection
        couples_ref = db.collection("couples")
        couples_watch = couples_ref.on_snapshot(upload_data_couples)
        print("   ✅ Listener 'couples' đã khởi động")
        
        # Listener cho couple_plans collection
        couple_plans_ref = db.collection("couple_plans")
        couple_plans_watch = couple_plans_ref.on_snapshot(upload_data_couplePlans)
        print("   ✅ Listener 'couple_plans' đã khởi động")
        
        print("🔄 Realtime sync đang hoạt động!")
        print("   → Mọi thay đổi trong Firebase sẽ tự động sync vào ChromaDB\n")
        
        return True
        
    except Exception as e:
        print(f"⚠️ Không thể khởi động Firebase sync: {e}")
        print("   Backend vẫn hoạt động nhưng không có realtime sync")
        import traceback
        traceback.print_exc()
        return False

# --- Local Development ---
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  RAG CHATBOT WITH PERSONALIZATION")
    print("="*60)
    
    # Kiểm tra xem có đang chạy trên Cloud Run không
    is_cloud_run = os.environ.get("K_SERVICE") is not None
    
    if is_cloud_run:
        print("\n☁️ Running on Cloud Run - Stateless mode")
        print("   → User data loaded ON-DEMAND từ Firebase")
        print("   → Không dùng pickle cache")
        print("   → Không cần Firebase listeners\n")
    else:
        print("\n💻 Running on Local - Stateful mode")
        
        # Bước 1: Build initial data (nếu chưa có)
        build_initial_data()
        
        # Bước 2: Khởi động Firebase Realtime Sync
        start_firebase_sync()
    
    # Bước 3: Start server
    port = int(os.environ.get("PORT", 8080))
    print(f"\n🚀 Starting server on http://0.0.0.0:{port}")
    print(f"📖 Health check: http://localhost:{port}/health")
    print(f"💬 Chat endpoint: http://localhost:{port}/chat")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=True)
