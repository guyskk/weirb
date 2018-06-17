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


async def stream(data):
    yield data
