from validr import T
from weirb import require, route, raises
from weirb.error import ServiceError


class EchoError(ServiceError):
    """Echo Error"""
    status = 400
    code = 'Echo.Error'


class EchoService:

    echo_times = require('config.echo_times')

    @raises(EchoError)
    async def method_echo(
        self,
        text: T.str.default('')
    ) -> T.dict(text=T.str):
        """A echo method"""
        if text == 'error':
            raise EchoError('I echo an error')
        text = text * self.echo_times
        return dict(text=text)

    @route.get('/echo')
    @route('/echo/echo', methods=['GET', 'POST'])
    async def get_echo(self):
        text = self.request.query.get('text') or ''
        self.response.json(dict(
            text=text * self.echo_times,
        ))
