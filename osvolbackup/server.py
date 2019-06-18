#
# This module provides the ServerInstance class that encapsulate some complex server instances related operations
#

from __future__ import print_function
from novaclient import client as nova_client
from glanceclient import client as glance_client
from cinderclient import client as cinder_client
from osvolbackup.osauth import get_session, VERSION
from osvolbackup.verbose import vprint
from sys import stderr
from json import loads, dumps
from time import time, sleep
from datetime import datetime
from .project import Project


class ServerInstance(object):

    max_secs_gbi = 300
    poll_delay = 10

    def __init__(self, serverName=None, to_project=None):
        self.session = session = get_session()
        self.nova = nova_client.Client(VERSION, session=session)
        self.glance = glance_client.Client(VERSION, session=session)
        self.cinder = cinder_client.Client(VERSION, session=session)
        self.instance = None
        try:
            instance = self.nova.servers.get(serverName)
        except nova_client.exceptions.NotFound:
            instance = self.get_by_name(serverName)
        self.instance = instance
        server_info = instance.to_dict()
        self.networks = instance.networks

        # Check if server is volumed backed
        self.volume_list = server_info.get('os-extended-volumes:volumes_attached')
        if len(self.volume_list) == 0:
            print("Server has no volumes attached!", file=stderr)
            exit(2)

    def stop(self):
        if self.instance.status != 'SHUTOFF':
            vprint("Stopping server")
            self.instance.stop()
            vprint("Waiting for server stop")
            self._wait_for(self.instance, ('ACTIVE',), 'SHUTOFF', timeout=60)

    def get_by_name(self, serverName):
        instance_list = self.nova.servers.list(search_opts={"name": serverName, "all_tenants": True}, limit=2)
        if len(instance_list) == 0:
            raise ServerNotFound(serverName)
            exit(1)

        if len(instance_list) > 1:
            print("More than one server with name: %s\nPlease provide and id" % serverName, file=stderr)
            exit(2)

        server = instance_list[0]
        return server

    def get_volumes(self):
        vol_list = []
        for volume in self.volume_list:
            vol_id = volume['id']
            vol_size = self.cinder.volumes.get(vol_id).size
            vol_list.append({"id": vol_id, "size": vol_size})
        return vol_list

    def backup(self, name=None):
        server_info = self.instance.to_dict()
        if name:
            server_backup_name = name
        else:
            server_backup_name = server_info['id'] + '_'+datetime.now().isoformat()+"_backup"

        backup_start_time = datetime.now().isoformat()

        #   1. Attempt to freeze the server I/O
        #   2. Perform a snapshot of every volume attached to the server
        #   3. Create an empty image that olds references to the snapshots from 2
        #   4. Attempt to unfreeze the server I/O
        vprint("Creating backup image for server", self.instance.name)
        self.flavor = self.nova.flavors.get(self.instance.flavor['id']).name
        server_backup_image_id = self.instance.create_image(server_backup_name)
        image_info = self.glance.images.get(server_backup_image_id)
        block_device_mapping = loads(image_info['block_device_mapping'])
        for mapping in block_device_mapping:
            snapshot_list = [mapping['snapshot_id'] for mapping in block_device_mapping]

        # The image is no longer needed, we backup based on the snapshots
        self.glance.images.delete(server_backup_image_id)
        vprint("Deleting backup image after capturing snapshot list")

        backup_list = []
        for vol_number, snapshot_id in enumerate(snapshot_list):
            vprint("Getting snapshot info:", snapshot_id)
            snapshot_info = self.cinder.volume_snapshots.get(snapshot_id).to_dict()
            volume_id = snapshot_info['volume_id']
            # Attach OSVB metadata to first volume
            if vol_number == 0:
                volume = self.cinder.volumes.get(volume_id)
                project_name = Project(volume.to_dict()['os-vol-tenant-attr:tenant_id']).project.name
                metadata = {
                    "osvb_version": "1",
                    "osvb_name": self.instance.name,
                    "osvb_flavor": self.flavor,
                    "osvb_network": dumps(self.networks),
                    "osvb_project": project_name,
                    }
                self.cinder.volumes.set_metadata(volume, metadata)
            # We store some metada usefull for restore
            backup_tags = {
                "backup_time": backup_start_time,
                "vol_index": vol_number,
            }
            # https://github.com/openstack/python-cinderclient/blob/master/cinderclient/v2/volume_backups.py#L42
            vprint("Creating backup from snapshot (%dG)" % snapshot_info['size'])
            #  backup_cinder = cinder_client.Client(VERSION, session=self.project_session)
            backup_name = 'osvb_' + self.instance.id
            backup = self.cinder.backups.create(
                volume_id=volume_id, snapshot_id=snapshot_id, force=True, name=backup_name,
                description=dumps(backup_tags)
            )
            backup_list.append(backup)

            #  for backup_number, backup in enumerate(backup_list):
            vprint("Waiting for backup %s to complete..." % backup.id)
            self._wait_for(backup, ('creating',), 'available')
            backup_metadata_filename = "%s_%d.json" % (server_backup_name, vol_number)
            vprint("Volume backup completed.")
            vprint("Saving metadata backup file", backup_metadata_filename)
            with open(backup_metadata_filename, 'w') as meta_file:
                meta_file.write(dumps(self.cinder.backups.export_record(backup.id), indent=4))
            vprint("Deleting snapshot after backup")
            self.cinder.volume_snapshots.delete(backup.snapshot_id)

        vprint("Backup completed.")

    # Borrowed from https://github.com/Akrog/cinderback/blob/master/cinderback.py
    def _wait_for(self, resource, allowed_states, expected_states=None, timeout=None):
        """Waits for a resource to come to a specific state.
        :param resource: Resource we want to wait for
        :param allowed_states: iterator with allowed intermediary states
        :param expected_states: states we expect to have at the end, if None
                                is supplied then anything is good.
        :param need_up: If wee need backup service to be up and running
        :return: The most updated resource
        """
        if timeout:
            deadline = time() + timeout
        else:
            deadline = time() + (self.max_secs_gbi * resource.size)
        while resource.status in allowed_states:
            sleep(self.poll_delay)
            if deadline <= time():
                raise TimeoutError(what=resource)
            resource = resource.manager.get(resource.id)

        if expected_states and resource.status not in expected_states:
            raise UnexpectedStatus(what=resource, intermediate=allowed_states, final=expected_states)

        return resource


class ServerException(Exception):
    def __init__(self, what, *args, **kwargs):
        super(ServerException, self).__init__(*args, **kwargs)
        self.what = what

    def __str__(self):
        return u'%s: %s' % (self.__class__.__name__, self.what)


class UnexpectedStatus(ServerException):
    def __init__(self, what, intermediate='', final='', *args, **kwargs):
        super(UnexpectedStatus, self).__init__(what, *args, **kwargs)
        self.intermediate = intermediate
        self.final = final

    def __str__(self):
        if self.intermediate or self.final:
            steps = (' [intermediate: %s, final: %s]' % (self.intermediate, self.final))
        else:
            steps = ''
        return (u'%s: Status is %s%s' %
                (self.__class__.__name__, self.what.status, steps))


class ServerNotFound(ServerException):
    pass


class TooManyFound(ServerException):
    pass


class TimeoutError(ServerException):
    pass
