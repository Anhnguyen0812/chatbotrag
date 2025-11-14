"""
Simple User Data Storage - Không dùng ChromaDB
Lưu thông tin user vào pickle files, giống như prepare_data.py
"""

import os
import pickle
from typing import Dict, List
from langchain.schema import Document

# Directory để lưu user data
USER_DATA_DIR = "user_data"

def ensure_user_data_dir():
    """Tạo thư mục user_data nếu chưa có"""
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)
        print(f"✅ Đã tạo thư mục {USER_DATA_DIR}")

def get_user_data_file(user_id: str) -> str:
    """Lấy đường dẫn file pickle của user"""
    ensure_user_data_dir()
    return os.path.join(USER_DATA_DIR, f"{user_id}.pkl")

def user_exists(user_id: str) -> bool:
    """Kiểm tra user có tồn tại không"""
    return os.path.exists(get_user_data_file(user_id))

def create_user_data(user_id: str, text: str):
    """Tạo data mới cho user"""
    if user_exists(user_id):
        print(f"⚠️ User {user_id} đã tồn tại")
        return False
    
    # Lưu dạng dict để tránh phụ thuộc phiên bản pydantic/langchain khi unpickle
    documents = [{
        "page_content": text,
        "metadata": {"user_id": user_id, "doc_id": user_id}
    }]
    file_path = get_user_data_file(user_id)
    
    with open(file_path, 'wb') as f:
        pickle.dump(documents, f)
    
    print(f"✅ Đã tạo data cho user {user_id}")
    return True

def update_user_data(user_id: str, text: str, text_id: str):
    """Thêm/cập nhật thông tin vào user data"""
    file_path = get_user_data_file(user_id)
    
    # Load existing documents (list of dicts); migrate if needed
    if user_exists(user_id):
        try:
            with open(file_path, 'rb') as f:
                documents = pickle.load(f)
            # Migration: nếu là Document, chuyển sang dict
            if documents and isinstance(documents[0], Document):
                documents = [{
                    "page_content": d.page_content,
                    "metadata": dict(d.metadata)
                } for d in documents]
        except (EOFError, pickle.UnpicklingError) as e:
            print(f"⚠️ Lỗi đọc file pickle cho user {user_id}: {e}")
            print(f"🔧 Tạo lại file mới")
            documents = []
    else:
        print(f"⚠️ User {user_id} chưa tồn tại, tạo mới")
        documents = []
    
    # Kiểm tra xem text_id đã tồn tại chưa
    existing_doc = None
    for i, doc in enumerate(documents):
        if doc.get('metadata', {}).get('doc_id') == text_id:
            existing_doc = i
            break
    
    # Tạo document mới (dict)
    new_doc = {
        "page_content": text,
        "metadata": {"user_id": user_id, "doc_id": text_id}
    }
    
    if existing_doc is not None:
        # Cập nhật
        documents[existing_doc] = new_doc
        print(f"✅ Đã cập nhật doc {text_id} cho user {user_id}")
    else:
        # Thêm mới
        documents.append(new_doc)
        print(f"✅ Đã thêm doc {text_id} cho user {user_id}")
    
    # Lưu lại
    with open(file_path, 'wb') as f:
        pickle.dump(documents, f)
    
    return True

def delete_user_data(user_id: str, text_id: str):
    """Xóa một document khỏi user data"""
    if not user_exists(user_id):
        print(f"⚠️ User {user_id} không tồn tại")
        return False
    
    file_path = get_user_data_file(user_id)
    
    try:
        with open(file_path, 'rb') as f:
            documents = pickle.load(f)
        # Migration nếu cần
        if documents and isinstance(documents[0], Document):
            documents = [{
                "page_content": d.page_content,
                "metadata": dict(d.metadata)
            } for d in documents]
    except (EOFError, pickle.UnpicklingError) as e:
        print(f"⚠️ Lỗi đọc file pickle cho user {user_id}: {e}")
        print(f"🔧 Không thể xóa vì file bị lỗi")
        return False
    
    # Lọc bỏ document cần xóa
    documents = [doc for doc in documents if doc.get('metadata', {}).get('doc_id') != text_id]
    
    # Lưu lại
    with open(file_path, 'wb') as f:
        pickle.dump(documents, f)
    
    print(f"✅ Đã xóa doc {text_id} từ user {user_id}")
    return True

def delete_user(user_id: str):
    """Xóa toàn bộ data của user"""
    file_path = get_user_data_file(user_id)
    
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"✅ Đã xóa user {user_id}")
        return True
    
    print(f"⚠️ User {user_id} không tồn tại")
    return False

def get_user_data(user_id: str) -> List[Document]:
    """Lấy tất cả documents của user"""
    if not user_exists(user_id):
        return []
    
    file_path = get_user_data_file(user_id)
    
    try:
        with open(file_path, 'rb') as f:
            documents = pickle.load(f)
    except (EOFError, pickle.UnpicklingError) as e:
        print(f"⚠️ Lỗi đọc file pickle cho user {user_id}: {e}")
        print(f"🔧 Trả về danh sách rỗng")
        return []

    # Trả về List[Document] từ nguồn dict; nếu file cũ (Document) thì migrate và lưu lại
    changed = False
    docs_out: List[Document] = []
    for d in documents:
        if isinstance(d, Document):
            # migrate
            docs_out.append(d)
            changed = True
        else:
            docs_out.append(Document(page_content=d.get("page_content", ""), metadata=d.get("metadata", {})))
    if changed:
        # lưu lại theo dict để lần sau an toàn
        dicts = [{"page_content": doc.page_content, "metadata": dict(doc.metadata)} for doc in docs_out]
        with open(file_path, 'wb') as f:
            pickle.dump(dicts, f)
    return docs_out

def search_user_data(user_id: str, query: str, k: int = 3) -> List[Document]:
    """
    Simple search: Tìm documents có chứa từ khóa
    (Không dùng vector embeddings, chỉ keyword matching)
    """
    documents = get_user_data(user_id)
    
    if not documents:
        return []
    
    # Simple keyword matching (lowercase)
    query_lower = query.lower()
    
    # Score mỗi document
    scored_docs = []
    for doc in documents:
        content_lower = doc.page_content.lower()
        
        # Đếm số từ khóa xuất hiện
        score = 0
        for word in query_lower.split():
            if word in content_lower:
                score += content_lower.count(word)
        
        if score > 0:
            scored_docs.append((score, doc))
    
    # Sort theo score giảm dần
    scored_docs.sort(key=lambda x: x[0], reverse=True)
    
    # Trả về top k
    return [doc for score, doc in scored_docs[:k]]

def list_all_users() -> List[str]:
    """Lấy danh sách tất cả user IDs"""
    ensure_user_data_dir()
    
    users = []
    for filename in os.listdir(USER_DATA_DIR):
        if filename.endswith('.pkl'):
            user_id = filename[:-4]  # Remove .pkl
            users.append(user_id)
    
    return users

def get_stats() -> Dict:
    """Thống kê dữ liệu"""
    users = list_all_users()
    total_docs = 0
    
    for user_id in users:
        docs = get_user_data(user_id)
        total_docs += len(docs)
    
    return {
        "total_users": len(users),
        "total_documents": total_docs,
        "users": users
    }

# Test functions
if __name__ == "__main__":
    print("=== TEST SIMPLE USER DATA STORAGE ===\n")
    
    # Test 1: Create
    print("Test 1: Tạo user mới")
    create_user_data("test_user", "Tên: Nguyễn Văn A, sinh nhật: 25/12/1995")
    
    # Test 2: Update
    print("\nTest 2: Thêm thông tin")
    update_user_data("test_user", "Người yêu tên: Trần Thị B", "partner_info")
    update_user_data("test_user", "Kế hoạch: Đi Đà Lạt 25/12", "plan_dalat")
    
    # Test 3: Get
    print("\nTest 3: Lấy dữ liệu")
    docs = get_user_data("test_user")
    print(f"Có {len(docs)} documents:")
    for doc in docs:
        print(f"  - {doc.page_content[:50]}...")
    
    # Test 4: Search
    print("\nTest 4: Tìm kiếm")
    results = search_user_data("test_user", "người yêu", k=2)
    print(f"Tìm thấy {len(results)} kết quả:")
    for doc in results:
        print(f"  - {doc.page_content}")
    
    # Test 5: Stats
    print("\nTest 5: Thống kê")
    stats = get_stats()
    print(f"Total users: {stats['total_users']}")
    print(f"Total docs: {stats['total_documents']}")
    
    # Test 6: Delete
    print("\nTest 6: Xóa document")
    delete_user_data("test_user", "plan_dalat")
    
    print("\nTest 7: Xóa user")
    delete_user("test_user")
    
    print("\n=== HOÀN THÀNH ===")
