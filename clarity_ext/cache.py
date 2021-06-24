import requests_cache
from requests_cache import CachedSession
from requests_cache.backends import BaseCache, BaseStorage

class CustomCache(BaseCache):
    """Wrapper for higher-level cache operations. In most cases, the only thing you need
    to specify here is which storage class(es) to use.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.redirects = CustomStorage(**kwargs)
        self.responses = CustomStorage(**kwargs)

class CustomStorage(BaseStorage):
    """Dict-like interface for lower-level backend storage operations"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __getitem__(self, key):
        pass

    def __setitem__(self, key, value):
        pass

    def __delitem__(self, key):
        pass

    def __iter__(self):
        pass

    def __len__(self):
        pass

    def clear(self):
        pass







class CustomCachedSession(CachedSession):
    def __init__(self, *args, **kwargs):
        print(args, kwargs)
        super().__init__(*args, **kwargs)



def use_requests_cache(cache_name):
    """Turns on caching for the requests library"""
    requests_cache.install_cache(
        cache_name,
        allowable_methods=('GET', 'POST', 'DELETE', 'PUT'),
        session_factory=CustomCachedSession)

