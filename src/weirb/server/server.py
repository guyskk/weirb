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
import signal
import time
from multiprocessing import Process

from newio import socket, spawn
from newio_kernel import Runner
from gunicorn.reloader import Reloader

from .parser import RequestParser
from .worker import Worker

__all__ = ("serve",)


LOG = logging.getLogger(__name__)


def serve(app, config):
    server = Server(app, config)
    server.start()


GREEN = 2
BLUE = 75
PURPLE = 140
RED = 9

DEFAULT_FIELD_STYLES = {
    "asctime": {"color": GREEN},
    "hostname": {"color": PURPLE},
    "levelname": {"color": "black", "bold": True},
    "name": {"color": BLUE},
    "process": {"color": PURPLE},
    "programname": {"color": BLUE},
}

DEFAULT_LEVEL_STYLES = {
    "spam": {"color": GREEN, "faint": True},
    "success": {"color": GREEN, "bold": True},
    "verbose": {"color": GREEN},
    "debug": {"color": GREEN},
    "info": {},
    "notice": {},
    "error": {"color": RED},
    "critical": {"color": RED},
    "warning": {"color": "yellow"},
}


class Server:
    def __init__(self, app, config):
        self.app = app
        self.config = config
        self.debug = config.debug
        self.num_process = config.num_process
        self._runner = Runner(
            monitor_enable=self.config.newio_monitor_enable,
            monitor_host=self.config.newio_monitor_host,
            monitor_port=self.config.newio_monitor_port,
        )
        self._init_serv_sock()
        self._init_processes()
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
        flags = fcntl.fcntl(serv_sock.fileno(), fcntl.F_GETFD)
        flags |= fcntl.FD_CLOEXEC
        fcntl.fcntl(serv_sock.fileno(), fcntl.F_SETFD, flags)
        print(f"* Server listening at http://{host}:{port}")
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
        if not extra_files:
            extra_files = set()
        else:
            extra_files = set(extra_files)
        if self.app.config_path:
            extra_files.add(self.app.config_path)
        reloader = Reloader(callback=self._reload, extra_files=extra_files)
        reloader.start()
        print("* Reloader started")

    def _process(self, i):
        pid = os.getpid()
        LOG.info(f"Process#{i} pid={pid} started")
        try:
            self._runner(self._serve_forever())
        except KeyboardInterrupt:
            pass
        except Exception as ex:
            LOG.exception(ex)
        finally:
            LOG.info(f"Process#{i} pid={pid} exited")

    def _reload(self, filename):
        if self._reloading:
            return
        print(f"* Detected change in {filename!r}, reloading")
        self._reloading = True
        for p in self._processes:
            os.kill(p.pid, signal.SIGINT)
        self._stop_processes()

    def _stop_processes(self, timeout=0.3):
        deadline = time.monotonic() + timeout
        for i, p in enumerate(self._processes, 1):
            my_timeout = deadline - time.monotonic()
            if my_timeout > 0:
                p.join(timeout=my_timeout)
            if p.is_alive():
                LOG.info(f"Process#{i} pid={p.pid} force terminated")
                p.terminate()
            p.join()

    def start(self):
        LOG.info(f"Starting {self.num_process} processes")
        for p in self._processes:
            p.start()
        self._start_reloader()
        for p in self._processes:
            try:
                p.join()
            except KeyboardInterrupt:
                LOG.info("Shutting down processes")
                break
        self._stop_processes()
        if self._reloading:
            os.execv(sys.executable, [sys.executable] + sys.argv)

    async def _serve_forever(self):
        async with self._serv_sock:
            while True:
                cli_sock, cli_addr = await self._serv_sock.accept()
                LOG.debug("Accept connection from {}:{}".format(*cli_addr))
                worker = Worker(self.app, self._parse_request, cli_sock, cli_addr)
                await spawn(worker.main())
