from typing import List, Tuple, AsyncIterable, Any
from zope.interface import Interface, Attribute, implementer


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
