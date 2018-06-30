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
    def __init__(self, services, server_name):
        self.services = services
        self.server_name = server_name
        url_map = []
        for service in services:
            for handler in service.handlers:
                for route in handler.routes:
                    url_map.append(Rule(
                        route.path,
                        methods=route.methods,
                        endpoint=handler,
                    ))
        self.url_map = Map(url_map)

    @functools.lru_cache(maxsize=1024)
    def lookup(self, path, method):
        url = self.url_map.bind(server_name=self.server_name)
        try:
            handler, arguments = url.match(path_info=path, method=method)
        except WZ_NotFound as ex:
            raise NotFound() from None
        except WZ_MethodNotAllowed as ex:
            raise MethodNotAllowed() from None
        except WZ_RequestRedirect as ex:
            raise HttpRedirect(ex.new_url, status=ex.code)
        return handler, arguments
