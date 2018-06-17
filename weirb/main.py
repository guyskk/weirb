# import click
# import importlib

# from .config import Config
# from .error import ConfigError, AppNotFound
# from .server import run


# def _import_app(module_app):
#     if ':' not in module_app:
#         raise AppNotFound(f'invalid module:app {module_app!r}')
#     module, app = module_app.split(':', maxsplit=1)
#     try:
#         module = importlib.import_module(module)
#     except ImportError:
#         raise AppNotFound(f'module {module!r} not found')
#     app = getattr(module, app, None)
#     if app is None:
#         raise AppNotFound(f'app {app!r} not found in module {module!r}')
#     return app


# @click.command()
# @click.argument('module_app')
# @click.option('--debug/--no-debug', required=False,
#               help='Debug or not')
# @click.option('--host', required=False,
#               help='Listening host')
# @click.option('--port', type=int, required=False,
#               help='Listening port')
# @click.option('--reloader/--no-reloader', '-r', default=None, required=False,
#               help='Enable reloader or not')
# @click.option('--num-process', '-n', type=int, required=False,
#               help='Number of processes')
# @click.option('--config-path', '-c', required=False,
#               help='config path')
# @click.pass_context
# def main(ctx, module_app, config_path, reloader, **cli_config):
#     """Run App"""
#     cli_config['reloader_enable'] = reloader
#     try:
#         config = Config.load(config_path, cli_config)
#     except ConfigError as ex:
#         ctx.abort(str(ex))
#     try:
#         app = _import_app(module_app)
#     except AppNotFound as ex:
#         ctx.abort(str(ex))
#     run(app, config)


# if __name__ == '__main__':
#     main()
