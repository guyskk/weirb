from validr import T, Invalid, validator
from newio_kernel.kernel import MONITOR_DEFAULT_HOST, MONITOR_DEFAULT_PORT

_LOG_LEVELS = {
    'DEBUG',
    'INFO',
    'WARN',
    'WARNING',
    'ERROR',
    'CRITICAL',
}


@validator(string=True)
def loglevel_validator(parser):
    def validate_loglevel(value):
        try:
            value = value.upper()
        except Exception:
            raise Invalid(f'Invalid log level {value!r}')
        if value not in _LOG_LEVELS:
            raise Invalid(f'Unknown log level {value!r}')
        return value
    return validate_loglevel


INTERNAL_VALIDATORS = dict(
    loglevel=loglevel_validator,
)


class InternalConfig:
    """Weirb Internal Config"""
    root_path = T.str.optional
    server_name = T.str.optional
    print_config = T.bool.default(False)
    print_plugin = T.bool.default(False)
    print_service = T.bool.default(False)
    print_handler = T.bool.default(False)

    debug = T.bool.default(False)
    host = T.str.default('127.0.0.1')
    port = T.int.min(0).default(8080)
    backlog = T.int.min(1).default(1024)
    num_process = T.int.min(1).default(1)
    xheaders = T.bool.default(False)

    request_header_timeout = T.float.min(-1).default(60)
    request_body_timeout = T.float.min(-1).default(60)
    request_keep_alive_timeout = T.float.min(-1).default(90)
    request_max_header_size = T.int.min(0).default(8 * 1024)
    request_max_body_size = T.int.min(0).default(1024 * 1024)
    request_header_buffer_size = T.int.min(1).default(1024)
    request_body_buffer_size = T.int.min(1).default(16 * 1024)

    response_json_pretty = T.bool.optional
    response_json_sort_keys = T.bool.default(False)

    reloader_enable = T.bool.optional
    reloader_extra_files = T.str.optional

    logger_level = T.loglevel.optional
    logger_colored = T.bool.optional
    logger_format = T.str.default(
        '%(levelname)1.1s %(asctime)s P%(process)-5s '
        '%(name)s:%(lineno)-4d %(message)s')
    logger_datefmt = T.str.default('%Y-%m-%d %H:%M:%S')

    newio_monitor_enable = T.bool.optional
    newio_monitor_host = T.str.default(MONITOR_DEFAULT_HOST)
    newio_monitor_port = T.int.default(MONITOR_DEFAULT_PORT)

    def __post_init__(self):
        self.root_path = self.root_path.rstrip('/') + '/'
        if not self.logger_level:
            self.logger_level = 'DEBUG' if self.debug else 'INFO'
        if self.logger_colored is None:
            self.logger_colored = self.debug
        if self.reloader_enable is None:
            self.reloader_enable = self.debug
        if self.newio_monitor_enable is None:
            self.newio_monitor_enable = self.debug
        if self.response_json_pretty is None:
            self.response_json_pretty = self.debug
        if self.response_json_sort_keys is None:
            self.response_json_sort_keys = self.debug
