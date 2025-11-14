from simpleUserData import get_user_data, search_user_data


class SimpleUserCollection:
    """Wrapper class để tương thích với code cũ"""
    
    def __init__(self, user_id):
        self.user_id = user_id
    
    def similarity_search(self, query, k=3):
        """Search documents (simple keyword matching)"""
        return search_user_data(self.user_id, query, k)
    
    def get(self):
        """Get all documents as list of Document objects"""
        return get_user_data(self.user_id)


def get_user_collection(user_id):
    """Lấy user collection (simple pickle-based)"""
    return SimpleUserCollection(user_id)

