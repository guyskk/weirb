from validr import T
from weirb import Response
from weirb_hrpc import require, http_request, http_response


class EchoService:

    echo_times = require('config.echo_times')

    async def method_echo(
        self,
        text: T.str.default('')
    ) -> T.dict(text=T.str):
        """A echo method"""
        text = text * self.echo_times
        return dict(text=text)

    @http_request
    @http_response
    async def method_hecho(self, request):
        """A http echo method"""
        text = request.querys.get('text', '') * self.echo_times
        return Response(200, body=text.encode('utf-8'))
