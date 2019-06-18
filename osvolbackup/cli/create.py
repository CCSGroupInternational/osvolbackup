from __future__ import print_function
from sys import stderr
from ..server import ServerInstance, ServerNotFound
from ..project import Project
from osvolbackup.osauth import get_session, VERSION
from novaclient import client as nova_client
from neutronclient.v2_0 import client as neutron_client
from pprint import pprint
import click



@click.command()
@click.argument('servername')
@click.argument('volume_list')
@click.argument('network_list')
@click.argument('flavor')
@click.argument('to-project')
def create(servername, volume_list, network_list, to_project, flavor):
    session = get_session(to_project)
    nova = nova_client.Client(VERSION, session=session)
    neutron = neutron_client.Client(session=session)
    try:
        ServerInstance(servername)
    except ServerNotFound:
        pass
    else:
        print("There is already a server instance with that name", file=stderr)
        exit(2)
    block_device_mapping = {}
    volumes = volume_list.split(',')
    for i, volume_id in enumerate(volumes):
        dev_name = "vd" + chr(ord('a') + i)
        block_device_mapping[dev_name] = volume_id
    nics = []
    project = Project(to_project)
    project_id = project.project.to_dict()['id']
    for network in network_list.split(','):
        if '=' in network:
            net_name, net_ip = network.split("=")
            pprint(neutron.list_networks(name=net_name, project_id=project_id)['networks'][0]['id'])
            net_id = neutron.list_networks(name=net_name, project_id=project_id)['networks'][0]['id']
            nic_info = {'net-id': net_id, 'v4-fixed-ip': net_ip}
            if net_ip == "dynamic":
                del nic_info['v4-fixed-ip']
        else:
            nic_info = {'port-id': network}
        nics.append(nic_info)
    flavor = nova.flavors.find(name=flavor)    # name to id
    target_session = get_session(to_project)
    target_nova = nova_client.Client(VERSION, session=target_session)
    server = target_nova.servers.create(
        name=servername, image=None, flavor=flavor, block_device_mapping=block_device_mapping, nics=nics
    )
    print("Server was restored into instance", server.id)
