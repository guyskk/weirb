import os
import sys
import os.path
import shutil
from importlib import import_module
from pathlib import Path
from collections import deque

import click

from . import __version__
from . import App
from .error import ConfigError, AppNotFound
from .helper import get_current_app_name
from .shell import HrpcShell

PROJECT_ROOT = Path(__file__).parent.parent


@click.group()
def cli():
    """Weirb HRPC CLI"""


def _dynamic_command():
    return cli.command(context_settings=dict(
        allow_extra_args=True,
        ignore_unknown_options=True
    ))


@cli.command()
def version():
    """Show CLI version"""
    click.echo(__version__)


@cli.command()
@click.option('--name', prompt='Project Name',
              help='Project name')
@click.option('-s', '--simple', default=False, is_flag=True,
              prompt='Use simple layout?',
              help='Use simple or standard layout')
@click.pass_context
def new(ctx, name, simple=False):
    """Create new project"""
    try:
        os.makedirs(name)
    except FileExistsError:
        ctx.fail(f'Project {name} already exists')
    path = Path(os.path.abspath(name))
    click.echo(f'directory {str(path)!r} created')
    module_name = name.replace('-', '_')
    if simple:
        src = PROJECT_ROOT / 'example' / 'hello.py'
        dst = path / f'{module_name}.py'
        shutil.copy(src, dst)
    else:
        src = PROJECT_ROOT / 'example' / 'echo'
        dst = path / module_name
        shutil.copytree(src, dst)
    click.echo('done!')


def _parse_config_options(tokens):
    """
    eg: ['--debug', '--port', '8899', 'xxx=yyy']
    """
    tokens = deque(tokens)
    config = {}
    prev = None

    def _take_prev():
        nonlocal prev
        if prev is not None:
            config[prev] = True
            prev = None

    while tokens:
        token = tokens.popleft()
        if token.startswith('--'):
            token = token[2:]
            _take_prev()
        parts = token.split('=', maxsplit=1)
        if len(parts) == 2:
            config[parts[0]] = parts[1]
            _take_prev()
        else:
            if prev is not None:
                config[prev] = parts[0]
                prev = None
            else:
                prev = parts[0]
    _take_prev()

    config = {k.replace('-', '_'): v for k, v in config.items()}
    return config


def _create_app(ctx, name):
    if not name:
        try:
            name = get_current_app_name()
        except AppNotFound as ex:
            ctx.fail(str(ex))
    sys.path.append(os.path.abspath(os.getcwd()))
    try:
        import_module(name)
    except ModuleNotFoundError as ex:
        ctx.fail(f'App not found, {ex}')
    config = _parse_config_options(ctx.args)
    try:
        app = App(name, **config)
    except ConfigError as ex:
        ctx.fail(str(ex))
    return app


@_dynamic_command()
@click.option('--name', type=str, required=False,
              help='App name')
@click.pass_context
def run(ctx, name=None):
    """Run app server, use `--<key>=<value>` to set config"""
    app = _create_app(ctx, name)
    app.run()


@_dynamic_command()
@click.option('--name', type=str, required=False,
              help='App name')
@click.pass_context
def shell(ctx, name=None):
    """Run app shell, use `--<key>=<value>` to set config"""
    app = _create_app(ctx, name)
    HrpcShell(app).start()


if __name__ == '__main__':
    cli()
