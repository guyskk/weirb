import json
from weirb import Response as HttpResponse


class Response:
    def __init__(self, *, headers=None, result=None):
        if headers is None:
            self.headers = {}
        else:
            self.headers = headers
        self.result = result

    def to_http(self, indent=4):
        text = json.dumps(self.result, ensure_ascii=False, indent=indent)
        response = HttpResponse(status=200, body=text.encode('utf-8'))
        response.headers['Content-Type'] = 'application/json;charset=utf-8'
        for k, v in self.headers.items():
            response.headers[f'Hrpc-{k}'] = str(v)
        return response


class ErrorResponse(Response):
    def __init__(self, error, headers=None, data=None):
        if headers is None:
            self.headers = {}
        else:
            self.headers = headers
        self.headers['error'] = error.error
        self.result = dict(
            message=error.message,
            data=data,
        )
