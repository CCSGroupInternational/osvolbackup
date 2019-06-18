from __future__ import print_function

import click
from ..server import ServerInstance
from ..project import Project
from sys import stderr


@click.command()
@click.argument('projectname')
def project(projectname):
    project_info = Project(projectname)
    failed_backups = []
    for instance in project_info.get_servers():
        server = ServerInstance(instance.id)
        try:
            server.backup()
        except Exception as e:
            print("Backup failed\n" + str(e), file=stderr)
            failed_backups.append(server)
            continue
    if failed_backups:
        print("Servers which failed to backup:")
        for server in failed_backups:
            print(server.instance.id, server.instance.name)