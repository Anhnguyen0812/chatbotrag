"""
Firebase Realtime Listeners
Lắng nghe thay đổi realtime từ Firebase Firestore
"""

from firebaseClient import db, initialize_firebase
from manageDataFirebase.uploadData import (
    upload_data_users,
    upload_data_couples,
    upload_data_couplePlans
)

def start_listeners():
    """
    Bắt đầu lắng nghe các thay đổi từ Firebase
    Chỉ sử dụng khi chạy local hoặc dedicated server
    """
    if db is None:
        print("❌ Firestore client chưa được khởi tạo")
        return False
    
    try:
        # Listener cho users collection
        users_ref = db.collection("users")
        users_watch = users_ref.on_snapshot(upload_data_users)
        print("✅ Listener 'users' đã khởi động")
        
        # Listener cho couples collection
        couples_ref = db.collection("couples")
        couples_watch = couples_ref.on_snapshot(upload_data_couples)
        print("✅ Listener 'couples' đã khởi động")
        
        # Listener cho couple_plans collection
        couple_plans_ref = db.collection("couple_plans")
        couple_plans_watch = couple_plans_ref.on_snapshot(upload_data_couplePlans)
        print("✅ Listener 'couple_plans' đã khởi động")
        
        return True
        
    except Exception as e:
        print(f"❌ Lỗi khởi động listeners: {e}")
        return False

def stop_listeners():
    """Dừng tất cả listeners (nếu cần)"""
    # Chromadb listeners tự động unsubscribe khi process kết thúc
    print("🛑 Dừng listeners...")

if __name__ == "__main__":
    print("=== BẮT ĐẦU FIREBASE LISTENERS ===")
    
    # Khởi tạo Firebase nếu chưa có
    if db is None:
        initialize_firebase()
    
    # Bắt đầu listeners
    if start_listeners():
        print("\n✅ Tất cả listeners đang hoạt động")
        print("Nhấn Ctrl+C để dừng...")
        
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Đang dừng listeners...")
            stop_listeners()
    else:
        print("❌ Không thể khởi động listeners")
