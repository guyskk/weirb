import logging
import functools

from werkzeug.routing import (
    Map, Rule,
    NotFound as WZ_NotFound,
    MethodNotAllowed as WZ_MethodNotAllowed,
    RequestRedirect as WZ_RequestRedirect,
)

from .error import NotFound, MethodNotAllowed, HttpRedirect

LOG = logging.getLogger(__name__)


class Router:
    def __init__(self, services, root_path=''):
        self.services = services
        print(services)
        self.root_path = root_path.rstrip('/') + '/'
        url_map = []
        for service in services:
            for handler in service.handlers:
                for route in handler.routes:
                    path = self.root_path + route['path'].strip('/')
                    url_map.append(Rule(
                        path,
                        endpoint=handler,
                        host=route['host'],
                        methods=route['methods'],
                    ))
        self.url_map = Map(url_map)

    @functools.lru_cache(maxsize=1024)
    def lookup(self, host, path, method):
        url = self.url_map.bind(server_name=host)
        try:
            handler, arguments = url.match(path_info=path, method=method)
        except WZ_NotFound as ex:
            raise NotFound(str(ex)) from None
        except WZ_MethodNotAllowed as ex:
            raise MethodNotAllowed(str(ex)) from None
        except WZ_RequestRedirect as ex:
            raise HttpRedirect(ex.new_url, status=ex.code)
        return handler, arguments
