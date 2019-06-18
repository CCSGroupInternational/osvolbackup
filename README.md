# OpenStack Server Volumes Backup and Restore Tool

This command line utility can be used to backup/restore OpenStack volume backed server instances using Cinder backup service.

## Screenshot
![Screenshot](imgs/osvolbackup_test.png)

## Features

- Live instance backup
    - See `consistency restrictions` below
    - Embed essential metadata in backup description
    - Export backup volume metadata to file

## Requirements

- Python2.7+ and the OpenStack API libraries
- OpenStack environment with volume backed server instances
- OS environment variables set for the admin project `(source stackrc)`
- [Cinder backup service] properly configured
- Tested on [RedHat Open Stack Platform 13], should work on other OpenStack Queens based distributions

[Cinder backup service]: https://docs.openstack.org/cinder/queens/configuration/block-storage/backup-drivers.html
[RedHat Open Stack Platform 13 ]: https://access.redhat.com/documentation/en-us/red_hat_openstack_platform/13/

## :warning: Live Backup Consistency Restrictions :warning:

Live backup consistency of openstack images is dependent in the following conditions:

1. When using kvm/libvirt, guests must have the [Qemu guest agent] installed, backups will succeed if the agent is not available, consistency will depend in the guest IO activity during the snapshot»
2. Nova API create image function does [not wait for snapshot creation] before unfreezing the I/O, consistency will depend on the block device driver snapshot technology, it may depend on the guest IO activity during the snapshot creation

[Qemu guest agent]: https://wiki.libvirt.org/page/Qemu_guest_agent
[not wait for snapshot creation]: https://github.com/openstack/nova/blob/master/nova/compute/api.py#L3094


## How to install
```sh
pip install --user osvolbackup
```

## How to use
```sh
# Backup a server instance
osvolbackup server instance_name

# Restore from last backup
osvolbackup server instance_name --restore last

# Restore from last backup but using a different network config
osvolbackup server instance_name --restore last --network net_name:ip_address


## How to run from source
```sh
git clone https://github.com/CCSGroupInternational/osvolbackup.git
cd osvolbackup.git
pip install --user -rrequirements.txt
python -m osvolbackup server «server_name»
```

## How to test:
```sh
# Create a test server
export SERVER_ID=test_server
tests/create-test-server.sh

# Create the backup
VERBOSE=1 python -m osvolbackup server ${SERVER_ID}

# Delete the test instance
openstack server delete ${SERVER_ID}
openstack volume delete ${SERVER_ID}_boot

# We use the instance uuid because the server name was deleted
INSTANCE_ID=$(openstack volume backup list | grep ${SERVER_ID}|cut -d" " -f4)
# Restore with the original config
VERBOSE=1 python -m osvolbackup server $INSTANCE_ID --restore last
# Restore with a different network config
VERBOSE=1 python -m osvolbackup server $INSTANCE_ID --restore last --network net1:10.3.1.99
```

## Copyright

© 2019 CCS Group International, distributed under the [Apache-2 license].

[Apache-2 license]: LICENSE
