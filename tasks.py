from invoke import task


@task
def build(ctx):
    ctx.run('python setup.py sdist')
