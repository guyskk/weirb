# flake8: noqa
try:
    from contextlib import AsyncExitStack
    from contextlib import *
except ImportError:
    from ._contextlib import *
