from __future__ import print_function
from sys import stderr

import click
from ..server import ServerInstance, ServerNotFound, TooManyFound
from ..backup import BackupGroup, BackupNotFound


@click.command()
@click.argument('servername')
@click.option('--restore', type=str, default=None)
@click.option('--network', type=str, default=None)
@click.option('--force', is_flag=True, default=False)
@click.option('--to-project', type=str, default=None)
@click.option('--skip-vm', is_flag=True, default=False)
def server(servername, restore, force, network, to_project, skip_vm):
    server = None
    try:
        server = ServerInstance(servername)
    except ServerNotFound:
        if not restore:
            print("No server found with name: %s" % servername, file=stderr)
            exit(1)
    except TooManyFound:
        print("Multiple servers found with name: %s" % servername, file=stderr)
        exit(2)
    if not restore:
        server.backup()
    else:
        try:
            backup = BackupGroup(servername)
        except BackupNotFound:
            print("No backup found for server: %s" % servername, file=stderr)
            exit(3)
        backup.select_by_tag(restore)
        if server:
            if not force:
                print("An instance with that name already exists.", file=stderr)
                print("Restore can only be performed using --force", file=stderr)
                exit(2)
            if backup.get_volumes() != server.get_volumes():
                print("Volume list on backup does not match running instance!", file=stderr)
                print(backup.get_volumes(), server.get_volumes(), file=stderr)
                print("Manual restore is required",  file=stderr)
                exit(3)
            server.stop()
        backup.restore(server, network, to_project, skip_vm)
