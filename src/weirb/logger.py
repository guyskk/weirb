import logging
import coloredlogs


GREEN = 2
BLUE = 75
PURPLE = 140
RED = 9

DEFAULT_FIELD_STYLES = {
    'asctime': {'color': GREEN},
    'hostname': {'color': PURPLE},
    'levelname': {'color': 'black', 'bold': True},
    'name': {'color': BLUE},
    'process': {'color': PURPLE},
    'programname': {'color': BLUE}
}

DEFAULT_LEVEL_STYLES = {
    'spam': {'color': GREEN, 'faint': True},
    'success': {'color': GREEN, 'bold': True},
    'verbose': {'color': GREEN},
    'debug': {'color': GREEN},
    'info': {},
    'notice': {},
    'error': {'color': RED},
    'critical': {'color': RED},
    'warning': {'color': 'yellow'}
}


def config_logging(config):
    level = config.logger_level
    fmt = config.logger_format
    datefmt = config.logger_datefmt
    if config.logger_colored:
        coloredlogs.install(
            level=level, fmt=fmt, datefmt=datefmt,
            field_styles=DEFAULT_FIELD_STYLES,
            level_styles=DEFAULT_LEVEL_STYLES,
        )
    else:
        logging.basicConfig(level=level, format=fmt, datefmt=datefmt)
