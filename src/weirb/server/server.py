"""PEP 1024 -- AWSGI

async with app.context() as ctx:
    response = await ctx(request)
    # (1) send response headers to socket
    async for chunk in response.body:
        # (2) send response body to socket
"""
import os
import sys
import fcntl
import logging

from newio import socket, open_nursery, Runner
from gunicorn.reloader import Reloader

from .parser import RequestParser
from .worker import Worker

__all__ = ("serve",)


LOG = logging.getLogger(__name__)


def serve(app, config):
    server = Server(app, config)
    server.start()


class Server:
    def __init__(self, app, config):
        self.app = app
        self.config = config
        self.debug = config.debug
        self._runner = Runner(monitor=self.config.newio_monitor_enable)
        self._pid = os.getpid()
        self._init_serv_sock()
        self._reloading = False

    def _parse_request(self, cli_sock, cli_addr):
        parser = RequestParser(
            cli_sock,
            cli_addr,
            header_timeout=self.config.request_header_timeout,
            body_timeout=self.config.request_body_timeout,
            keep_alive_timeout=self.config.request_keep_alive_timeout,
            max_header_size=self.config.request_max_header_size,
            max_body_size=self.config.request_max_body_size,
            header_buffer_size=self.config.request_header_buffer_size,
            body_buffer_size=self.config.request_body_buffer_size,
        )
        return parser.parse()

    def _init_serv_sock(self):
        host = self.config.host
        port = self.config.port
        backlog = self.config.backlog
        serv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        serv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        flags = fcntl.fcntl(serv_sock.fileno(), fcntl.F_GETFD)
        flags |= fcntl.FD_CLOEXEC
        fcntl.fcntl(serv_sock.fileno(), fcntl.F_SETFD, flags)
        print(f"* Server PID={self._pid} listening at http://{host}:{port}")
        serv_sock.bind((host, port))
        serv_sock.listen(backlog)
        self._serv_sock = serv_sock

    def _start_reloader(self):
        if not self.config.reloader_enable:
            return
        extra_files = self.config.reloader_extra_files
        if not extra_files:
            extra_files = set()
        else:
            extra_files = set(extra_files)
        if self.app.config_path:
            extra_files.add(self.app.config_path)
        reloader = Reloader(callback=self._reload, extra_files=extra_files)
        reloader.start()
        print("* Reloader started")

    def _reload(self, filename):
        if self._reloading:
            return
        print(f"* Detected change in {filename!r}, reloading")
        self._reloading = True
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def start(self):
        self._start_reloader()
        try:
            self._runner(self._serve_forever())
        except KeyboardInterrupt:
            print(f"* Server PID={self._pid} stopped")

    async def _serve_forever(self):
        async with self._serv_sock:
            async with open_nursery() as nursery:
                while True:
                    cli_sock, cli_addr = await self._serv_sock.accept()
                    LOG.debug("Accept connection from {}:{}".format(*cli_addr))
                    worker = Worker(self.app, self._parse_request, cli_sock, cli_addr)
                    await nursery.spawn(worker.main(nursery))
