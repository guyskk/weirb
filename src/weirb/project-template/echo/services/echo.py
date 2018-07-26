from validr import T
from weirb import require, route, raises
from weirb.error import ServiceError


class EchoError(ServiceError):
    """Echo Error"""

    status = 400
    code = "Echo.Error"


class EchoService:

    echo_times = require("config.echo_times")

    @raises(EchoError)
    async def do_echo(self, text: T.str.default("")) -> T.dict(text=T.str):
        """A echo method"""
        if text == "error":
            raise EchoError("I echo an error")
        return {"text": text * self.echo_times}

    @route.get("/echo/echo")
    async def get_echo(self) -> T.dict(text=T.str):
        text = self.request.query.get("text") or ""
        return {"text": text * self.echo_times}
