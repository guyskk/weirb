from zope.interface import Interface, Attribute, implementer
from typing import List, Tuple, AsyncIterable
from .error import HttpError
from .helper import stream


class IResponse(Interface):
    status: int = Attribute('Status code')
    status_text: str = Attribute('Status text')
    version: str = Attribute('HTTP version')
    headers: List[Tuple[str, str]] = Attribute('Response headers')
    body: AsyncIterable = Attribute('Response body')
    chunked: bool = Attribute('Is chunked or not')
    keep_alive: bool = Attribute('Is keep alive or not')


@implementer(IResponse)
class AbstractResponse:

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    def __repr__(self):
        class_name = type(self).__name__
        return f'<{class_name} {self.status} {self.status_text}>'


class ErrorResponse(AbstractResponse):
    def __init__(self, error: HttpError):
        self._error = error
        self._body = str(error).encode('utf-8')
        self.status = error.status
        self.status_text = error.phrase
        self.version = 'HTTP/1.1'
        self.headers = [('Content-Length', len(self._body))]
        self.body = stream(self._body)
        self.chunked = False
        self.keep_alive = None
