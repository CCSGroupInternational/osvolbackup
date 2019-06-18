from .cli.create import create
from .cli.server import server
from .cli.project import project
from .cli import version
import click


@click.group()
@click.version_option(version=version)
def cli():
    pass


cli.add_command(server)
cli.add_command(project)
cli.add_command(create)

def main():
    cli()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        raise
