from validr import T

from weirb import App, Client
from weirb.error import HrpcInvalidParams


class EchoService:
    async def method_echo(self, text: T.str) -> T.dict(text=T.str):
        return dict(text=text)


def test_echo():
    app = App(__name__)
    client = Client(app)
    text = 'hello'
    res = client.call('/echo/echo', text=text)
    assert res.json == dict(text=text)
    res = client.call('/echo/echo')
    assert res.error == HrpcInvalidParams.code
