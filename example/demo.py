from weirb.helper import stream
from weirb import run, AbstractResponse


class ContextResponse(AbstractResponse):

    def __init__(self, text):
        self._body = text.encode('utf-8')
        self.status = 200
        self.status_text = 'OK'
        self.version = 'HTTP/1.1'
        self.headers = [('Content-Length', len(self._body))]
        self.body = stream(self._body)
        self.chunked = False
        self.keep_alive = None


async def app(request):
    if request.url == '/error':
        raise ValueError(request.url)
    return ContextResponse(f'welcome {request.url}')


if __name__ == '__main__':
    run(app, debug=True, reloader_enable=False)
