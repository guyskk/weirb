from typing import List, Tuple, AsyncIterable, Any
from zope.interface import Interface, Attribute, implementer

from ..error import HttpError
from ..helper import stream


class IResponse(Interface):
    status: int = Attribute('Status code')
    status_text: str = Attribute('Status text')
    version: str = Attribute('HTTP version')
    headers: List[Tuple[str, Any]] = Attribute('Response headers')
    body: AsyncIterable[bytes] = Attribute('Response body')
    chunked: bool = Attribute('Is chunked or not')
    keep_alive: bool = Attribute('Is keep alive or not')


@implementer(IResponse)
class AbstractResponse:
    """Abstract Response"""


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

    def __repr__(self):
        return f'<{type(self).__name__} {self.status} {self.status_text}>'
