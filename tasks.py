from pathlib import Path
from invoke import task


@task
def build(ctx):
    for f in Path('dist').glob('*'):
        f.unlink()
    ctx.run('python setup.py sdist')


@task
def publish(ctx):
    build(ctx)
    ctx.run('twine upload dist/*')
