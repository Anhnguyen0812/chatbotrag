from simpleUserData import update_user_data


def update_collection_exists(userId, text, textId):
    """Cập nhật/thêm thông tin vào user data"""
    update_user_data(userId, text, str(textId))


