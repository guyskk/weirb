class RawRequest:
    def __init__(
        self, *,
        method, url, version,
        headers, body,
        protocol, remote_ip,
        keep_alive,
    ):
        self.method = method
        self.url = url
        self.version = version
        self.headers = headers
        self.body = body
        self.protocol = protocol
        self.remote_ip = remote_ip
        self.keep_alive = keep_alive

    def __repr__(self):
        return f'<{type(self).__name__} {self.method} {self.url}>'
