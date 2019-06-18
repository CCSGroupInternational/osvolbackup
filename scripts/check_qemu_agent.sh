#!/bin/sh
active_servers=$(openstack server list --all-projects -fcsv -c ID -c Status |grep "ACTIVE"|cut -d"," -f1| tr -d '"')
rm -f ~/.missing_qemu_agent.new
for server in $active_servers
do
	echo Checking server $server
	eval $(openstack server show -f shell $server -c id -c name -c OS-EXT-SRV-ATTR:host -c OS-EXT-SRV-ATTR:instance_name|sed "s/inst-/instance-/g")
	echo Checking $name - $id
	result=$(ssh -T heat-admin@${os_ext_srv_attr_host} << _EOF_
	sudo virsh qemu-agent-command ${os_ext_srv_attr_instance_name} '{"execute":"guest-ping"}'
_EOF_
	)
	if [ "$result" == '{"return":{}}' ]; then
		echo ok
	else
		echo "not ok"
		echo "$name $id" >> ~/.missing_qemu_agent.new
	fi
done
mv ~/.missing_qemu_agent.new ~/.missing_qemu_agent
