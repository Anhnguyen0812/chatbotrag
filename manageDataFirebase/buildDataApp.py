from firebaseClient import db
from manageDataFirebase.buildCollectionUser import build_collection_user
from manageDataFirebase.updateCollectionExists import update_collection_exists
from google.cloud.firestore_v1.base_query import FieldFilter
from firebaseCache import get_cache
from datetime import datetime
import pytz


def build_data_app():
    users_ref = db.collection("users")
    couple_ref = db.collection("couples") 
    couplePlan_ref = db.collection("couple_plans")
    docs_user = users_ref.get()
    docs_couple = couple_ref.get()
    docs_couplePlan = couplePlan_ref.get()

    for docUser in docs_user:
        userId = docUser.id
        user_data = docUser.to_dict() or {}
        isPartner = user_data.get("partnerId") is not None
    
        textUser = (
            f"Thông tin của người dùng tên : {user_data.get('name', 'Không rõ')}, "
            f"ngày sinh nhật : {user_data.get('dateOfBirth', 'Không có')}, "
            f"Số điện thoại : {user_data.get('phoneNumber', 'Không có')}, "
            f"Giới tính : {user_data.get('gender', 'Không rõ')}"
        ) 

        build_collection_user(userID=userId, text=textUser)

        if (isPartner is True):
            partnerId = user_data.get('partnerId')
            startDate = str(user_data.get("startLoveDate", "không rõ"))
            coupleId = None
            for docCouple in docs_couple:
                couple_data = docCouple.to_dict() or {}
                if ((couple_data.get('user1Id') == userId and couple_data.get('user2Id') == partnerId) or (couple_data.get('user1Id') == partnerId and couple_data.get('user2Id') == userId)):
                    coupleId = docCouple.id
                    break
            if not coupleId:
                # Skip if no couple doc found for this pairing
                continue
            
            partner_data = db.collection("users").document(partnerId).get().to_dict() or {}
            partner_name = partner_data.get("name", "Không rõ")
            textCouple = f"Bạn bắt đầu hẹn hò vào thời gian : {startDate}, người yêu bạn tên là : {partner_name}"
            update_collection_exists(userId=userId, text=textCouple, textId=coupleId)

            for docPlan in docs_couplePlan:
                plan_data = docPlan.to_dict() or {}
                planId = docPlan.id
                if (plan_data.get('coupleId') == coupleId):
                    content = plan_data.get('title', '')
                    details= plan_data.get('details', '')
                    datePlan = plan_data.get('date', '')
                    timePlan = plan_data.get('time', '')
                    textPlan = f"Bạn có 1 kế hoạch: {content}, vào ngày: {datePlan} , giờ: {timePlan} với nội dung: {details}"
                    update_collection_exists(userId=userId, text=textPlan, textId=planId)


def get_user_data_from_firebase(user_id, use_cache=True):
    """
    Load dữ liệu của một user từ Firebase với caching.
    
    Args:
        user_id: ID của user cần lấy dữ liệu
        use_cache: True = dùng cache (default), False = force refresh từ Firebase
    
    Returns:
        list[str]: Danh sách các text documents về user
    """
    try:
        # ✅ Kiểm tra cache trước
        if use_cache:
            cache = get_cache()
            cached_data = cache.get(user_id)
            if cached_data is not None:
                return cached_data
        
        # ❌ Cache miss hoặc force refresh -> query Firebase
        print(f"🔄 Loading data from Firebase for user {user_id}...")
        user_docs = []
        
        # 1. Lấy thông tin user
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            print(f"⚠️ User {user_id} không tồn tại trong Firebase")
            return []
        
        user_data = user_doc.to_dict() or {}
        
        # Thêm thông tin cơ bản của user
        text_user = (
            f"Thông tin của người dùng tên : {user_data.get('name', 'Không rõ')}, "
            f"ngày sinh nhật : {user_data.get('dateOfBirth', 'Không có')}, "
            f"Số điện thoại : {user_data.get('phoneNumber', 'Không có')}, "
            f"Giới tính : {user_data.get('gender', 'Không rõ')}"
        )
        user_docs.append(text_user)
        
        # 2. Kiểm tra xem user có người yêu không
        partner_id = user_data.get('partnerId')
        if partner_id:
            # ✅ FIX: Convert Firestore Timestamp to Vietnam timezone
            start_date_raw = user_data.get("startLoveDate")
            if start_date_raw:
                try:
                    # Convert Firestore Timestamp to datetime
                    if hasattr(start_date_raw, 'timestamp'):
                        # It's a Firestore Timestamp
                        dt = datetime.fromtimestamp(start_date_raw.timestamp())
                    else:
                        # It's already a datetime or string
                        dt = start_date_raw if isinstance(start_date_raw, datetime) else datetime.fromisoformat(str(start_date_raw))
                    
                    # Convert to Vietnam timezone (UTC+7)
                    vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
                    dt_vietnam = dt.replace(tzinfo=pytz.UTC).astimezone(vietnam_tz)
                    
                    # Format as readable string
                    start_date = dt_vietnam.strftime("%d/%m/%Y")
                except Exception as e:
                    print(f"⚠️ Lỗi convert startLoveDate: {e}")
                    start_date = str(start_date_raw)
            else:
                start_date = "không rõ"
            
            # Lấy THÔNG TIN ĐẦY ĐỦ của người yêu (bao gồm cả thông tin chi tiết)
            partner_doc = db.collection("users").document(partner_id).get()
            if partner_doc.exists:
                partner_data = partner_doc.to_dict() or {}
                partner_name = partner_data.get("name", "Không rõ")
                partner_dob = partner_data.get("dateOfBirth", "Không có")
                partner_phone = partner_data.get("phoneNumber", "Không có")
                partner_gender = partner_data.get("gender", "Không rõ")
                
                # Thêm thông tin cơ bản về mối quan hệ
                text_couple = (
                    f"Bạn bắt đầu hẹn hò vào thời gian : {start_date}, "
                    f"người yêu bạn tên là : {partner_name}"
                )
                user_docs.append(text_couple)
                
                # ✅ THÊM: Thông tin chi tiết về người yêu
                text_partner_detail = (
                    f"Thông tin chi tiết về người yêu của bạn: "
                    f"Tên: {partner_name}, "
                    f"Ngày sinh: {partner_dob}, "
                    f"Số điện thoại: {partner_phone}, "
                    f"Giới tính: {partner_gender}"
                )
                user_docs.append(text_partner_detail)
                
                # 3. Tìm coupleId
                couples_ref = db.collection("couples")
                couples_query = couples_ref.where(filter=FieldFilter("user1Id", "==", user_id)).limit(1).get()
                
                couple_id = None
                for doc in couples_query:
                    couple_id = doc.id
                    break
                
                # Nếu không tìm thấy với user1Id, thử user2Id
                if not couple_id:
                    couples_query = couples_ref.where(filter=FieldFilter("user2Id", "==", user_id)).limit(1).get()
                    for doc in couples_query:
                        couple_id = doc.id
                        break
                
                # 4. Lấy các kế hoạch của couple
                if couple_id:
                    plans_ref = db.collection("couple_plans")
                    plans_query = plans_ref.where(filter=FieldFilter("coupleId", "==", couple_id)).get()
                    
                    for plan_doc in plans_query:
                        plan_data = plan_doc.to_dict() or {}
                        title = plan_data.get('title', '')
                        date_plan = plan_data.get('date', '')
                        timePlan = plan_data.get('time', '')
                        details= plan_data.get('details', '')
                        textPlan = f"Bạn có 1 kế hoạch: {title}, vào ngày: {date_plan} , giờ: {timePlan} với nội dung: {details}"
                        user_docs.append(textPlan)
                    
        # ✅ Lưu vào cache trước khi return
        if use_cache:
            cache = get_cache()
            cache.set(user_id, user_docs)
        
        return user_docs
        
    except Exception as e:
        print(f"❌ Lỗi khi load data từ Firebase cho user {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return []


if __name__ == "__main__":
    build_data_app()

        
