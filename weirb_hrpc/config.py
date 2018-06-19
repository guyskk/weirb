from validr import T
from weirb.config import loglevel_validator

INTERNAL_VALIDATORS = {'loglevel': loglevel_validator}


class InternalConfig:
    debug = T.bool.default(False)
    host = T.str.default('127.0.0.1')
    port = T.int.min(0).default(8080)
    backlog = T.int.min(1).default(1024)
    num_process = T.int.min(1).default(1)
    url_prefix = T.str.optional
    request_header_timeout = T.float.min(-1).default(60)
    request_body_timeout = T.float.min(-1).default(60)
    request_keep_alive_timeout = T.float.min(-1).default(90)
    request_max_header_size = T.int.min(0).default(8 * 1024)
    request_max_body_size = T.int.min(0).default(1024 * 1024)
    request_header_buffer_size = T.int.min(1).default(1024)
    request_body_buffer_size = T.int.min(1).default(16 * 1024)
    reloader_enable = T.bool.optional
    reloader_extra_files = T.str.optional
    logger_level = T.loglevel.optional
    logger_format = T.str.default(
        '%(asctime)s [%(process)s] %(levelname)-5s '
        '%(name)s:%(lineno)-4d %(message)s')
    logger_datefmt = T.str.default('%Y-%m-%d %H:%M:%S')

    # def __post_init__(self):
    #     if not self.logger_level:
    #         self.logger_level = 'DEBUG' if self.debug else 'INFO'
    #     if self.reloader_enable is None:
    #         self.reloader_enable = self.debug
