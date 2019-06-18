#
# This module provides the Instance class that encapsulate some complex server instances related operations
#

from __future__ import print_function
from json import loads
from neutronclient.v2_0 import client as neutron_client
from novaclient import client as nova_client
from cinderclient import client as cinder_client
from osvolbackup.server import ServerInstance, ServerNotFound
from osvolbackup.osauth import get_session, VERSION
from osvolbackup.verbose import vprint
from time import time, sleep


class BackupGroup(object):

    max_secs_gbi = 300
    poll_delay = 10

    def __init__(self, serverName):
        self.selected_metadata = None
        self.selected_backups = []
        self.selected_volumes = []
        session = self.session = get_session()
        self.neutron = neutron_client.Client(session=session)
        self.nova = nova_client.Client(VERSION, session=session)
        self.cinder = cinder_client.Client(VERSION, session=session)
        try:
            server = ServerInstance(serverName)
        except ServerNotFound:
            name = 'osvb_'+serverName
        else:
            name = 'osvb_'+server.instance.id
        self.backup_list = self.cinder.backups.list(search_opts={"name": name})
        self.volume_map = {}

        if len(self.backup_list) == 0:
            raise BackupNotFound(serverName)

        # Load metadata from the backup description field
        self.backup_meta_data = backup_meta_data = {}
        for backup in self.backup_list:
            meta_data = loads(backup.description)
            backup_meta_data[backup.id] = meta_data
            self.volume_map[backup.id] = {"id": backup.volume_id, "size": backup.size}
        self.available_backups = sorted(set([b['backup_time'] for b in backup_meta_data.values()]))

    def select_by_tag(self, tag):
        if tag == 'last':
            selected_backup_timestamp = self.available_backups[-1]
        else:
            raise BackupTooMany(tag)

        # Get volumes associated with the selected backup
        for backup_id, backup_meta in self.backup_meta_data.iteritems():
            if backup_meta['backup_time'] == selected_backup_timestamp:
                self.selected_backups.append(backup_id)
                self.selected_volumes.append(self.volume_map[backup_id])
                self.selected_metadata = backup_meta

    def get_volumes(self):
        return self.selected_volumes

    def restore(self, server=None, network=None, to_project=None, skip_vm=False):
        # flavor = self.nova.flavors.find(name=self.selected_metadata['flavor'])

        new_volume_list = self._create_volumes(self.selected_volumes, to_project)

        # Restore the volumes
        block_device_mapping = {}

        for i, backup_id in enumerate(self.selected_backups):
            vol_index = self.backup_meta_data[backup_id]['vol_index']
            new_volume_id = new_volume_list[i].id
            vprint("Restoring from backup", backup_id, "to volume", new_volume_id)
            dev_name = "vd" + chr(ord('a') + vol_index)
            block_device_mapping[dev_name] = new_volume_id

            restore = self.cinder.restores.restore(backup_id=backup_id, volume_id=new_volume_id)
            restored_volume = self.cinder.volumes.get(restore.volume_id)
            self._wait_for(restored_volume, ('restoring-backup',), 'available')
            # We need to get again to refresh the metadata
            restored_volume = self.cinder.volumes.get(restore.volume_id)
            if vol_index == 0:
                if not skip_vm:
                    name = restored_volume.metadata['osvb_name']
                    flavor = restored_volume.metadata['osvb_flavor']
                    flavor = self.nova.flavors.find(name=flavor)    # name to id
                    saved_networks = loads(restored_volume.metadata['osvb_network'])
        if not skip_vm:
            nics = []
            if network is not None:
                net_name, net_ip = network.split("=")
                net_id = self.neutron.list_networks(name=net_name)['networks'][0]['id']
                nic_info = {'net-id': net_id, 'v4-fixed-ip': net_ip}
                nics.append(nic_info)
            else:
                for network_name, network_ips in saved_networks.iteritems():
                    nic_info = {}
                    nic_info['net-id'] = self.neutron.list_networks(name=network_name)['networks'][0]['id']
                    nic_info['v4-fixed-ip'] = network_ips[0]
                    nics.append(nic_info)
            target_session = get_session(to_project)
            target_nova = nova_client.Client(VERSION, session=target_session)
            server = target_nova.servers.create(
                name=name, image=None, flavor=flavor, block_device_mapping=block_device_mapping, nics=nics
            )
            print("Server was restored into instance", server.id)

    def _create_volumes(self, volume_list, to_project):
        """ Create volumes based """
        vprint("Creating volumes for the instance restore")
        target_session = get_session(to_project)
        target_cinder = cinder_client.Client(VERSION, session=target_session)
        vol_list = []
        for volume in volume_list:
            vprint("Creating %dG volume" % volume['size'])
            new_volume = target_cinder.volumes.create(volume['size'])
            self._wait_for(new_volume, ('creating',), 'available')
            vol_list.append(new_volume)
        return vol_list

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


class BackupException(Exception):

    def __init__(self, what, *args, **kwargs):
        super(BackupException, self).__init__(*args, **kwargs)
        self.what = what

    def __str__(self):
        return u'%s: %s' % (self.__class__.__name__, self.what)


class UnexpectedStatus(BackupException):
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


class BackupNotFound(BackupException):
    pass


class BackupTooMany(BackupException):
    pass
