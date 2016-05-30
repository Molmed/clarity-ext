import requests_cache
import os
import shutil


# http://stackoverflow.com/a/3013910/282024
def lazyprop(fn):
    attr_name = '_lazy_' + fn.__name__
    @property
    def _lazyprop(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)
    return _lazyprop

# Monkey patch the sqlite cache in requests_cache so that it
default_dbdict_set_item = requests_cache.backends.storage.dbdict.DbPickleDict.__setitem__
default_dbdict_get_item = requests_cache.backends.storage.dbdict.DbPickleDict.__getitem__
AUTH_HEADER = 'Authorization'


def dbdict_set_item(self, key, item):
    store = item[0]
    if AUTH_HEADER in store.request.headers:
        store.request.headers[AUTH_HEADER] = '***'
    default_dbdict_set_item(self, key, item)


def dbdict_get_item(self, key):
    item = default_dbdict_get_item(self, key)
    store = item[0]
    if AUTH_HEADER in store.request.headers and \
                      store.request.headers[AUTH_HEADER] != '***':
        raise ValueError("Auth header was serialized")
    return item

requests_cache.backends.storage.dbdict.DbPickleDict.__setitem__ = dbdict_set_item
requests_cache.backends.storage.dbdict.DbPickleDict.__getitem__ = dbdict_get_item


def use_requests_cache(cache):
    requests_cache.install_cache(cache, allowable_methods=('GET', 'POST', 'DELETE', 'PUT'))


def clean_directory(path, skip=[]):
    to_remove = (os.path.join(path, file_or_dir)
                 for file_or_dir in os.listdir(path)
                 if file_or_dir not in skip)
    for item in to_remove:
        if os.path.isdir(item):
            shutil.rmtree(item)
        else:
            os.remove(item)


def single(seq):
    """Returns the first element in a list, throwing an exception if there is an unexpected number of items"""
    if len(seq) != 1:
        raise Exception("Unexpected number of items in the list ({})".format(len(seq)))
    return seq[0]
