import os
import os.path
import importlib


def find_version():
    try:
        from pkg_resources import get_distribution, DistributionNotFound
    except ImportError:
        return 'unknown'
    try:
        pkg = get_distribution('weirb')
    except DistributionNotFound:
        return 'dev'
    return pkg.version


def import_all_modules(import_name):
    root = importlib.import_module(import_name)
    yield root
    if import_name == '__main__':
        return
    for root_path in set(root.__path__):
        for root, dirs, files in os.walk(root_path):
            if '__init__.py' in files:
                module = root[len(root_path):].replace('/', '.')
                if module:
                    module = f'{import_name}.{module}'
                else:
                    module = import_name
                yield importlib.import_module(module)
            for filename in files:
                if filename != '__init__.py' and filename.endswith('.py'):
                    module = os.path.splitext(os.path.join(root, filename))[0]
                    module = module[len(root_path):].replace('/', '.')
                    yield importlib.import_module(f'{import_name}{module}')
