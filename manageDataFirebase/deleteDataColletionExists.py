from simpleUserData import delete_user_data


def delete_data_collection_exists(userId, textID):
    """Xóa document khỏi user data"""
    delete_user_data(userId, textID)