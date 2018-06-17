import toml
from validr import T, Compiler, Invalid, validator
from terminaltables import AsciiTable

from .error import ConfigError

LOG_LEVELS = {
    'DEBUG',
    'INFO',
    'WARN',
    'WARNING',
    'ERROR',
    'CRITICAL',
}

CONFIG_SCHEMA = dict(
    debug=T.bool.default(False),
    host=T.str.default('127.0.0.1'),
    port=T.int.min(0).default(8080),
    backlog=T.int.min(1).default(1024),
    num_process=T.int.min(1).default(1),
    request_header_timeout=T.float.min(-1).default(60),
    request_body_timeout=T.float.min(-1).default(60),
    request_keep_alive_timeout=T.float.min(-1).default(90),
    request_max_header_size=T.int.min(0).default(8 * 1024),
    request_max_body_size=T.int.min(0).default(1024 * 1024),
    request_header_buffer_size=T.int.min(1).default(1024),
    request_body_buffer_size=T.int.min(1).default(16 * 1024),
    reloader_enable=T.bool.optional,
    reloader_extra_files=T.str.optional,
    logger_level=T.loglevel.default('INFO'),
    logger_format=T.str.default(
        '%(asctime)s [%(process)s] %(levelname)-5s %(name)s:%(lineno)-4d %(message)s'),
    logger_datefmt=T.str.default('%Y-%m-%d %H:%M:%S'),
)


@validator(string=True)
def loglevel_validator(parser):
    def validate_loglevel(value):
        try:
            value = value.upper()
        except:
            raise Invalid(f'Invalid log level {value!r}')
        if value not in LOG_LEVELS:
            raise Invalid(f'Unknown log level {value!r}')
        return value
    return validate_loglevel


def _read_config(config_path):
    if config_path is None:
        try:
            with open('weirb.toml') as config_file:
                config_content = config_file.read()
        except FileNotFoundError:
            return {}
    else:
        try:
            with open(config_path) as config_file:
                config_content = config_file.read()
        except FileNotFoundError as ex:
            raise ConfigError(f'config file {config_path!r} not found!') from ex
    try:
        return toml.loads(config_content)
    except toml.TomlDecodeError as ex:
        msg = (f'failed to load config file {config_path!r}, '
               'it not valid TOML format!')
        raise ConfigError(msg) from ex


def _shorten(x, w=30):
    return (x[:w] + '...') if len(x) > w else x


def _load_config(config_path, cli_config):
    file_config = _read_config(config_path)
    final_config = {}
    errors = []
    compiler = Compiler(validators=dict(
        loglevel=loglevel_validator,
    ))
    for k, schema in CONFIG_SCHEMA.items():
        validate = compiler.compile(schema)
        value = cli_config.get(k, None)
        if value is None:
            value = file_config.get(k, None)
        try:
            value = validate(value)
        except Invalid as ex:
            errors.append((k, _shorten(repr(schema)), ex.message))
        else:
            final_config[k] = value
    if errors:
        data = [('Key', 'Schema', 'Error')] + errors
        msg = '\n' + AsciiTable(data).table
        raise ConfigError(msg)
    return final_config


class Config:

    def __init__(self, **kwargs):
        if kwargs['debug']:
            kwargs['logger_level'] = 'DEBUG'
            if kwargs['reloader_enable'] is None:
                kwargs['reloader_enable'] = True
        self.__dict__.update(kwargs)

    @staticmethod
    def load(cli_config):
        cfg = _load_config(None, cli_config)
        return Config(**cfg)
