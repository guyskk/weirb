from validr import T
from weirb import require


class EchoService:

    echo_times = require('config.echo_times')

    async def method_echo(
        self,
        text: T.str.default('')
    ) -> T.dict(text=T.str):
        """A echo method"""
        text = text * self.echo_times
        return dict(text=text)
