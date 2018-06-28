import logging
from weirb.error import NotFound, MethodNotAllowed
from .error import MethodNotFound

LOG = logging.getLogger(__name__)


class Router:
    def __init__(self, services, url_prefix=''):
        self.table = {}
        for s in services:
            self.table[s.name.lower()] = methods = {}
            for m in s.methods:
                methods[m.name.lower()] = m
        self.prefix = url_prefix.rstrip('/') + '/'

    def lookup(self, http_method, path):
        path = path.lower()
        if not path.startswith(self.prefix):
            raise NotFound()
        path = path[len(self.prefix):]
        parts = path.rsplit('/', maxsplit=1)
        if len(parts) < 2:
            raise NotFound()
        service, method = parts
        LOG.debug('request path parsed: service=%r, method=%r', service, method)
        if service not in self.table:
            raise NotFound()
        methods = self.table[service]
        if method not in methods:
            raise MethodNotFound()
        service_method = methods[method]
        if not service_method.is_http_request:
            if http_method != 'POST':
                raise MethodNotAllowed()
        return service_method
