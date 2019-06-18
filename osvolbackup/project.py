from __future__ import print_function
from osvolbackup.osauth import get_session, VERSION
from keystoneauth1.exceptions.http import NotFound
from keystoneclient.v3 import client as keystone_client
from novaclient import client as nova_client

# References:
#   https://ask.openstack.org/en/question/50087/list-all-servers-with-python-nova-client/?answer=50090#post-id-50090


class Project(object):

    def __init__(self, projectName):
        self.session = session = get_session()
        self.keystone = keystone_client.Client(session=session)
        self.nova = nova_client.Client(VERSION, session=session)
        try:
            project = self.keystone.projects.get(projectName)
        except NotFound:
            project_list = [project for project in self.keystone.projects.list() if project.name == projectName]
            if len(project_list) == 0:
                raise NotFound
            if len(project_list) > 1:
                raise ProjectTooManyFound(projectName)
            project = project_list[0]
        self.project = project

    def get_servers(self):
        search_opts = {
            'tenant_id': self.project.id,
            'all_tenants': True,
        }
        return self.nova.servers.list(search_opts=search_opts)


class ProjectException(Exception):
    def __init__(self, what, *args, **kwargs):
        super(ProjectException, self).__init__(*args, **kwargs)
        self.what = what

    def __str__(self):
        return u'%s: %s' % (self.__class__.__name__, self.what)


class ProjectNotFound(ProjectException):
    pass


class ProjectTooManyFound(ProjectException):
    pass

