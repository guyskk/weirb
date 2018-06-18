from weirb import run, Request, Response


class AppContext:

    def __init__(self, handler):
        self.handler = handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def __call__(self, raw_request):
        request = Request(raw_request)
        return await self.handler(request)


class App:

    def context(self):
        return AppContext(self.handler)

    async def handler(self, request):
        if request.url == '/error':
            raise ValueError(request.url)
        content = f'welcome {request.url}'.encode('utf-8')
        return Response(body=content)


if __name__ == '__main__':
    run(App(), debug=True, reloader_enable=False)
