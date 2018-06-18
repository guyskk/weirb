import click


@click.group()
def cli():
    pass


@cli.command()
def version():
    print('1.0.0')


if __name__ == '__main__':
    cli()
