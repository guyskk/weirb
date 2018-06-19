import os
import os.path
import shutil
from pathlib import Path
from collections import deque

import click

from . import __version__
from . import App


PROJECT_ROOT = Path(__file__).parent.parent


@click.group()
def cli():
    """Weirb HRPC CLI"""


@cli.command()
def version():
    """Show CLI version"""
    click.echo(__version__)


@cli.command()
@click.option('--name', prompt=True,
              help='Project name')
@click.option('-s', '--simple', is_flag=True, prompt=True,
              help='Use simple or standard layout')
@click.pass_context
def new(ctx, name, simple=False):
    """Create new project"""
    try:
        os.makedirs(name)
    except FileExistsError:
        ctx.fail(f'Project {name} already exists')
    path = Path(os.path.abspath(name))
    click.echo(f'directory {path!r} created')
    if simple:
        src = PROJECT_ROOT / 'example' / 'hello.py'
        dst = path / f'{name}.py'
        shutil.copy(src, dst)
    else:
        src = PROJECT_ROOT / 'example' / 'demo'
        dst = path / name
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
            else:
                prev = parts[0]
    _take_prev()

    config = {k.replace('-', '_'): v for k, v in config.items()}
    return config


@cli.command(context_settings=dict(
    allow_extra_args=True,
    ignore_unknown_options=True
))
@click.pass_context
def run(ctx):
    """Run app server, use `--<key>=<value>` to set config"""
    name = os.path.basename(os.getcwd()).replace('-', '_')
    app_exists = os.path.exists(name) or os.path.exists(f'{name}.py')
    if not app_exists:
        ctx.fail(f'App not found, is {name} directory or {name}.py exists?')
    config = _parse_config_options(ctx.args)
    print(config)
    app = App(name, **config)
    app.run()


if __name__ == '__main__':
    cli()
