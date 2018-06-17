"""PEP 1024 -- AWSGI

response = await application(request)
async with response:
    # write headers to socker
    async for chunk in response.body:
        # write chunk to socket
"""
import os
import sys
import fcntl
import logging
from multiprocessing import Process

from validr import Invalid
from newio import socket, spawn
from newio_kernel import run as run_task
from gunicorn.reloader import Reloader
import coloredlogs

from .error import ConfigError
from .config import Config
from .parser import RequestParser
from .worker import Worker

__all__ = ('run',)

LOG = logging.getLogger(__name__)


def run(app, **config):
    try:
        config = Config(**config)
    except Invalid as ex:
        raise ConfigError(ex.message) from None
    server = Server(app, config)
    server.run()


class Server:

    def __init__(self, app, config):
        self.app = app
        self.config = config
        self.debug = config.debug
        self.num_process = config.num_process
        self._init_loging()
        self._init_serv_sock()
        self._init_processes()

    def _parse_request(self, cli_sock, cli_addr):
        parser = RequestParser(
            cli_sock, cli_addr,
            header_timeout=self.config.request_header_timeout,
            body_timeout=self.config.request_body_timeout,
            keep_alive_timeout=self.config.request_keep_alive_timeout,
            max_header_size=self.config.request_max_header_size,
            max_body_size=self.config.request_max_body_size,
            header_buffer_size=self.config.request_header_buffer_size,
            body_buffer_size=self.config.request_body_buffer_size,
        )
        return parser.parse()

    def _init_loging(self):
        level = self.config.logger_level
        fmt = self.config.logger_format
        datefmt = self.config.logger_datefmt
        coloredlogs.install(level=level, fmt=fmt, datefmt=datefmt)

    def _init_serv_sock(self):
        host = self.config.host
        port = self.config.port
        backlog = self.config.backlog
        serv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        flags = fcntl.fcntl(serv_sock.fileno(), fcntl.F_GETFD)
        flags |= fcntl.FD_CLOEXEC
        fcntl.fcntl(serv_sock.fileno(), fcntl.F_SETFD, flags)
        LOG.info(f'Listening http://{host}:{port}!')
        serv_sock.bind((host, port))
        serv_sock.listen(backlog)
        self._serv_sock = serv_sock

    def _init_processes(self):
        self._processes = []
        for i in range(1, self.num_process + 1):
            p = Process(target=self._process, args=(i,))
            self._processes.append(p)

    def _start_reloader(self):
        if not self.config.reloader_enable:
            return
        extra_files = self.config.reloader_extra_files
        reloader = Reloader(
            callback=self._reload, extra_files=extra_files)
        reloader.start()
        print('* Reloader started')

    def _process(self, i):
        pid = os.getpid()
        LOG.info(f'Process#{i} pid={pid} started')
        try:
            run_task(self._serve_forever())
        except KeyboardInterrupt:
            pass
        except Exception as ex:
            LOG.exception(ex)
        finally:
            LOG.info(f'Process#{i} pid={pid} exited')

    def _reload(self, filename):
        print(f'* Detected change in {filename!r}, reloading')
        for p in self._processes:
            p.terminate()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def run(self):
        LOG.info(f'Starting {self.num_process} processes')
        for p in self._processes:
            p.start()
        self._start_reloader()
        for p in self._processes:
            try:
                p.join()
            except KeyboardInterrupt:
                LOG.info('Shutting down processes')

    async def _serve_forever(self):
        async with self._serv_sock:
            while True:
                cli_sock, cli_addr = await self._serv_sock.accept()
                LOG.debug('Accept connection from {}:{}'.format(*cli_addr))
                worker = Worker(
                    self.app, self._parse_request, cli_sock, cli_addr)
                await spawn(worker.main())
