from firebaseClient import db
from simpleUserData import create_user_data, user_exists


def build_collection_user(userID, text):
    """Tạo data cho user mới (dùng pickle thay vì ChromaDB)"""
    if user_exists(userID):
        print(f"⚠️ User {userID} đã tồn tại")
        return
    
    create_user_data(userID, text)

