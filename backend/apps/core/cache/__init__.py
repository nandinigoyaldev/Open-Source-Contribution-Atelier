from django.core.cache import caches

class MultiLevelCache:
    """
    A multi-level cache that checks L1 (memory) before L2 (Redis).
    This drastically reduces network I/O for hot endpoints like leaderboards.
    """
    def __init__(self, l1_name='l1_memory', l2_name='default'):
        self.l1 = caches[l1_name]
        self.l2 = caches[l2_name]

    def get(self, key, default=None):
        value = self.l1.get(key)
        if value is not None:
            return value

        value = self.l2.get(key)
        if value is not None:
            self.l1.set(key, value, timeout=60)
            return value

        return default

    def set(self, key, value, timeout=None):
        self.l2.set(key, value, timeout=timeout)
        
        l1_timeout = 60
        if timeout is not None and timeout < 60:
            l1_timeout = timeout
            
        self.l1.set(key, value, timeout=l1_timeout)

multi_level_cache = MultiLevelCache()
