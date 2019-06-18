# (osvb) OpenStack Server Volume Backup Description

This document provides a short description on how osvolbackup backups are stored.

# Backup Format
osvb uses the OpenStack cinder volume backup service, it does not use it exclusively, which means you can have both osvb and non-osvb backups in the same backup service.

## Backup Name

osvb_{instance_uuid}

`osvb_` to differentiate it from other backups and `instance_uuid` to associate backups with server, supporting duplicated server names

## Backup Description

The backup description is used as a container for the metadata that can be used to identify/filter the backups that need to be restore, it contains a JSON string with the following fields:

```json
"backup_time" : The backup start time
"vol_index" : Position in the instance attached volumes list
```
An unique (single or multi-volume) backup, is identified by backup name and backup_time keys.


### Volumes Metadata

Before backing up the volume, osvb will add to it the following properties to the first volume of the instance (JSON strings):
```json
"osvb_version": osb scheme version number, for metadata versioning
"osvb_name": instance name,
"osvb_flavor": instance flavor,
"osvb_network": network names and ip addresses,
"osvb_project": the project name
```