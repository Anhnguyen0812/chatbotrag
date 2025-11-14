from manageDataFirebase.getUserCollection import get_user_collection
from manageDataFirebase.buildCollectionUser import build_collection_user
from firebaseClient import db
from manageDataFirebase.updateCollectionExists import update_collection_exists
from manageDataFirebase.deleteDataColletionExists import delete_data_collection_exists
from simpleUserData import delete_user
"""
    Hàm này sẽ quét xem db của firebase có sự thay đổi về dữ liệu ko
    Nếu có sự thay đổi thì nó sẽ xem là dữ liệu mới hay update dữ liệu cũ để thực hiện đúng
    """


def upload_data_users(col_snapshot, changes, read_time):
    print("😀 users changing \n")
    for change in changes:
        document = change.document
        userId = document.id
        if (change.type.name == "ADDED"):
            print("😀 users add changing \n")
            data = document.to_dict()

            text = (
                f"Thông tin của người dùng tên : {data.get('name', 'Không rõ')}, "
                f"ngày sinh nhật : {data.get('dateOfBirth', 'Không có')}, "
                f"Số điện thoại : {data.get('phoneNumber', 'Không có')}, "
                f"Giới tính : {data.get('gender', 'Không rõ')}"
            ) 
            build_collection_user(userID=userId, text=text)  
        elif (change.type.name == "MODIFIED"):
            print("😀 users modified changing \n")
            data = document.to_dict()

            text = (
                f"Thông tin của người dùng tên : {data.get('name', 'Không rõ')}, "
                f"ngày sinh nhật : {data.get('dateOfBirth', 'Không có')}, "
                f"Số điện thoại : {data.get('phoneNumber', 'Không có')}, "
                f"Giới tính : {data.get('gender', 'Không rõ')}"
            ) 
            delete_data_collection_exists(userId=userId, textID=userId)
            update_collection_exists(userId=userId, text=text, textId=userId)
        elif (change.type.name == "REMOVED"):
            print("😀 users remove changing \n")
            delete_user(userId)


def upload_data_couples(col_snapshot, changes, read_time):
    print("😀 couples changing \n")
    for change in changes:
        document = change.document
        coupleId = document.id
        data = document.to_dict() or {}

        if change.type.name == "ADDED":
            print("😀 couples add changing \n")
            user1Id = data.get("user1Id")
            user2Id = data.get("user2Id")
            startDate = str(data.get("startDate", "không rõ"))

            if not user1Id or not user2Id:
                print(f"[ERROR] couples/{coupleId} thiếu user1Id hoặc user2Id")
                continue

            user2 = db.collection("users").document(user2Id).get().to_dict() or {}
            user1 = db.collection("users").document(user1Id).get().to_dict() or {}

            name2 = user2.get("name", "Không rõ")
            name1 = user1.get("name", "Không rõ")

            text1 = f"Bạn bắt đầu hẹn hò vào thời gian : {startDate}, người yêu bạn tên là : {name2}"
            text2 = f"Bạn bắt đầu hẹn hò vào thời gian : {startDate}, người yêu bạn tên là : {name1}"
            update_collection_exists(userId=user1Id, text=text1, textId=coupleId)
            update_collection_exists(userId=user2Id, text=text2, textId=coupleId)

        elif change.type.name == "REMOVED":
            print("😀 couples remove changing \n")
            # Best-effort cleanup: use stored coupleId as textID for both users if available
            user1Id = data.get("user1Id")
            user2Id = data.get("user2Id")
            if user1Id:
                delete_data_collection_exists(userId=user1Id, textID=coupleId)
            if user2Id:
                delete_data_collection_exists(userId=user2Id, textID=coupleId)


def upload_data_couplePlans(col_snapshot, changes, read_time):
    print("😀 couplePlans changing \n")
    for change in changes:
        document = change.document
        planId = document.id
        data = document.to_dict() or {}

        coupleId = data.get("coupleId")
        if not coupleId:
            print(f"[ERROR] couple_plans/{planId} thiếu coupleId")
            continue

        content = data.get("title", "")
        date = str(data.get("date", ""))
        time = str(data.get("time", ""))
        details = data.get("details", "")

        couple_doc = db.collection("couples").document(coupleId).get()
        if not couple_doc.exists:
            # Likely causes: wrong coupleId in plan, couple deleted, or race condition (plan added before couple created)
            print(f"[ERROR] Không tìm thấy document couples/{coupleId} (từ couple_plans/{planId})")
            continue

        couple_data = couple_doc.to_dict() or {}
        user1Id = couple_data.get("user1Id")
        user2Id = couple_data.get("user2Id")

        if not user1Id or not user2Id:
            print(f"[ERROR] couples/{coupleId} thiếu user1Id hoặc user2Id")
            continue

        if change.type.name == "ADDED":
            print("😀 couplePlans add changing \n")
            text = f"Bạn có 1 kế hoạch: {content}, vào ngày: {date} , giờ: {time} với nội dung: {details}"
            update_collection_exists(userId=user1Id, text=text, textId=planId)
            update_collection_exists(userId=user2Id, text=text, textId=planId)

        elif change.type.name == "REMOVED":
            print("😀 couplePlans remove changing \n")
            delete_data_collection_exists(userId=user1Id, textID=planId)
            delete_data_collection_exists(userId=user2Id, textID=planId)
