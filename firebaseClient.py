"""
Firebase Client Configuration
Khởi tạo Firebase Admin SDK để kết nối với Firestore
"""

import os
from firebase_admin import credentials, initialize_app, firestore, get_app
from typing import Optional

# Global Firestore client
db: Optional[firestore.client] = None

def initialize_firebase():
    """
    Khởi tạo Firebase Admin SDK
    Tự động phát hiện credentials từ environment hoặc file
    """
    global db
    
    try:
        # Kiểm tra xem đã khởi tạo chưa
        try:
            app = get_app()
            print("✅ Firebase đã được khởi tạo trước đó")
        except ValueError:
            # Chưa khởi tạo, tiến hành khởi tạo
            
            # Option 1: Sử dụng service account key file
            cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            
            if cred_path and os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                initialize_app(cred)
                print(f"✅ Firebase khởi tạo từ file: {cred_path}")
            else:
                # Option 2: Sử dụng default credentials (Cloud Run, Cloud Functions)
                initialize_app()
                print("✅ Firebase khởi tạo với default credentials")
        
        # Khởi tạo Firestore client
        db = firestore.client()
        print("✅ Firestore client sẵn sàng")
        
        return db
        
    except Exception as e:
        print(f"❌ Lỗi khởi tạo Firebase: {e}")
        raise

# Khởi tạo ngay khi import
try:
    db = initialize_firebase()
except Exception as e:
    print(f"⚠️ Cảnh báo: Không thể khởi tạo Firebase tự động: {e}")
    db = None
