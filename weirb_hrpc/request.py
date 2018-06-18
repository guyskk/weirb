class Request:
    def __init__(self, method, headers, params):
        self.method = method
        self.headers = headers
        self.params = params
