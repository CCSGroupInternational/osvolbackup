#!/bin/sh

set -eu

SERVER_IMAGE="cirros-0.4.0-x86_64-disk.qcow2"
SERVER_FLAVOR="m1.tiny"

echo Creating bootable volume for server ${SERVER_ID}
eval $(openstack volume create -fshell --prefix boot_volume_ --image ${SERVER_IMAGE} ${SERVER_ID}_boot --size 1 --bootable)

echo Creating server ${SERVER_ID}
eval $(openstack server create -fshell --prefix instance_ --flavor ${SERVER_FLAVOR} --volume ${boot_volume_id} ${SERVER_ID} --network net1)

#openstack server show ${instance_id}
