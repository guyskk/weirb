import logging
import coloredlogs


GREEN = 41
BLUE = 75
PURPLE = 140
RED = 9
GRAY = 240

DEFAULT_FIELD_STYLES = {
    "asctime": {"color": GREEN},
    "hostname": {"color": PURPLE},
    "levelname": {"color": GRAY, "bold": True},
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


def config_logging(import_name, config):
    level = config.logger_level
    fmt = config.logger_format
    datefmt = config.logger_datefmt
    colored_params = dict(
        fmt=fmt,
        datefmt=datefmt,
        field_styles=DEFAULT_FIELD_STYLES,
        level_styles=DEFAULT_LEVEL_STYLES,
    )
    level_loggers = [logging.getLogger("weirb"), logging.getLogger(import_name)]
    for logger in level_loggers:
        logger.setLevel(level)
    if config.logger_colored:
        # https://github.com/xolox/python-coloredlogs/issues/54
        coloredlogs.install(**colored_params)
        logging.getLogger().setLevel(logging.WARNING)
        for h in logging.getLogger().handlers:
            h.setLevel(logging.NOTSET)
    else:
        logging.basicConfig(format=fmt, datefmt=datefmt)
