from validr import T, Invalid, validator

from .error import ConfigError

_LOG_LEVELS = {"DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL"}


@validator(string=True)
def loglevel_validator(parser):
    def validate_loglevel(value):
        try:
            value = value.upper()
        except Exception:
            raise Invalid(f"Invalid log level {value!r}")
        if value not in _LOG_LEVELS:
            raise Invalid(f"Unknown log level {value!r}")
        return value

    return validate_loglevel


INTERNAL_VALIDATORS = dict(loglevel=loglevel_validator)


class InternalConfig:
    """Weirb Internal Config"""

    print_config = T.bool.default(False)
    print_plugins = T.bool.default(False)
    print_services = T.bool.default(False)
    print_handlers = T.bool.optional

    debug = T.bool.default(False)
    host = T.str.default("127.0.0.1")
    port = T.int.min(0).default(8080)
    root_path = T.str.optional
    server_name = T.str.optional
    backlog = T.int.min(1).default(1024)
    xheaders = T.bool.default(False)

    request_header_timeout = T.float.min(-1).default(60)
    request_body_timeout = T.float.min(-1).default(60)
    request_keep_alive_timeout = T.float.min(-1).default(90)
    request_max_header_size = T.int.min(0).default(8 * 1024)
    request_max_body_size = T.int.min(0).default(1024 * 1024)
    request_header_buffer_size = T.int.min(1).default(1024)
    request_body_buffer_size = T.int.min(1).default(16 * 1024)

    json_pretty = T.bool.optional
    json_sort_keys = T.bool.default(False)
    json_ujson_enable = T.bool.default(False)

    reloader_enable = T.bool.optional
    reloader_extra_files = T.str.optional

    logger_level = T.loglevel.optional
    logger_colored = T.bool.optional
    logger_format = T.str.default(
        "%(levelname)1.1s %(asctime)s "
        "%(name)s:%(lineno)-4d %(message)s"
    )
    logger_datefmt = T.str.default("%H:%M:%S")

    newio_monitor_enable = T.bool.optional

    def __post_init__(self):
        self.root_path = self.root_path.rstrip("/") + "/"
        # set default config on debug
        if not self.logger_level:
            self.logger_level = "DEBUG" if self.debug else "INFO"
        if self.logger_colored is None:
            self.logger_colored = self.debug
        if self.print_handlers is None:
            self.print_handlers = self.debug
        if self.reloader_enable is None:
            self.reloader_enable = self.debug
        if self.newio_monitor_enable is None:
            self.newio_monitor_enable = self.debug
        if self.json_pretty is None:
            self.json_pretty = self.debug
        if self.json_sort_keys is None:
            self.json_sort_keys = self.debug
        self.__check_ujson()

    def __check_ujson(self):
        if self.json_ujson_enable:
            try:
                import ujson  # noqa
            except ModuleNotFoundError:
                msg = "json_ujson_enable is set but ujson not installed!"
                raise ConfigError(msg) from None
