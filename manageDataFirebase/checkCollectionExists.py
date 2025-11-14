from simpleUserData import user_exists


def check_collection_exists(userId):
    """Kiểm tra user data có tồn tại không"""
    return user_exists(userId)