import re
import os
import sys
import os.path
import importlib
import inspect

from .error import AppNotFound

HTTP_REDIRECT_STATUS = [301, 302, 303, 307, 308]
HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}


async def stream(data):
    yield data


def is_terminal():
    return sys.stdout.isatty()


def shorten_text(x, width=30):
    return (x[:width] + "...") if len(x) > width else x


def concat_words(words, width=30, sep=", "):
    lines = []
    current_words = []
    remain_width = width
    for w in words:
        if (not current_words) or len(w) <= remain_width:
            current_words.append(w)
            remain_width -= len(w) + len(sep)
        else:
            lines.append(sep.join(current_words))
            current_words = [w]
            remain_width = width - (len(w) + len(sep))
    if current_words:
        lines.append(sep.join(current_words))
    return "\n".join(lines)


def find_version():
    try:
        from pkg_resources import get_distribution, DistributionNotFound
    except ImportError:
        return "unknown"
    try:
        pkg = get_distribution("weirb")
    except DistributionNotFound:
        return "dev"
    return pkg.version


def import_all_classes(import_name, pattern=".*"):
    visited = set()
    pattern = re.compile(pattern)
    for module in import_all_modules(import_name):
        for obj in vars(module).values():
            if not inspect.isclass(obj):
                continue
            if obj in visited:
                continue
            if pattern.fullmatch(obj.__name__):
                visited.add(obj)
                yield obj


def import_all_modules(import_name):
    root = importlib.import_module(import_name)
    yield root
    if import_name == "__main__":
        return
    for root_path in set(getattr(root, "__path__", [])):
        root_path = root_path.rstrip("/")
        for root, dirs, files in os.walk(root_path):
            root = root.rstrip("/")
            if "__init__.py" in files:
                module = root[len(root_path) :].replace("/", ".")
                if module:
                    module = f"{import_name}{module}"
                else:
                    module = import_name
                yield importlib.import_module(module)
            for filename in files:
                if filename != "__init__.py" and filename.endswith(".py"):
                    module = os.path.splitext(os.path.join(root, filename))[0]
                    module = module[len(root_path) :].replace("/", ".")
                    yield importlib.import_module(f"{import_name}{module}")


def get_current_app_name():
    name = os.path.basename(os.getcwd()).replace("-", "_")
    app_exists = os.path.exists(name) or os.path.exists(f"{name}.py")
    if not app_exists:
        msg = f"App not found, is {name} directory or {name}.py exists?"
        raise AppNotFound(msg)
    return name
