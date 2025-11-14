"""
Firebase Data Cache
Caching layer để giảm số lần query Firebase
"""
import time
from typing import Dict, List, Optional
from threading import Lock

class FirebaseDataCache:
    """Simple in-memory cache with TTL"""
    
    def __init__(self, ttl_seconds: int = 300):  # 5 minutes default
        self.cache: Dict[str, tuple[List[str], float]] = {}
        self.ttl_seconds = ttl_seconds
        self.lock = Lock()
    
    def get(self, user_id: str) -> Optional[List[str]]:
        """Get cached data if still valid"""
        with self.lock:
            if user_id in self.cache:
                data, timestamp = self.cache[user_id]
                
                # Check if cache is still valid
                if time.time() - timestamp < self.ttl_seconds:
                    print(f"✅ Cache HIT for user {user_id}")
                    return data
                else:
                    # Cache expired
                    print(f"⏰ Cache EXPIRED for user {user_id}")
                    del self.cache[user_id]
            
            print(f"❌ Cache MISS for user {user_id}")
            return None
    
    def set(self, user_id: str, data: List[str]):
        """Store data in cache"""
        with self.lock:
            self.cache[user_id] = (data, time.time())
            print(f"💾 Cached data for user {user_id}")
    
    def invalidate(self, user_id: str):
        """Invalidate cache for specific user"""
        with self.lock:
            if user_id in self.cache:
                del self.cache[user_id]
                print(f"🗑️ Cache invalidated for user {user_id}")
    
    def clear(self):
        """Clear all cache"""
        with self.lock:
            self.cache.clear()
            print("🗑️ All cache cleared")
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        with self.lock:
            return {
                "total_cached_users": len(self.cache),
                "ttl_seconds": self.ttl_seconds
            }

# Global cache instance
_firebase_cache = FirebaseDataCache(ttl_seconds=300)  # 5 minutes

def get_cache() -> FirebaseDataCache:
    """Get global cache instance"""
    return _firebase_cache
