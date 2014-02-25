from djangostack import DjangoStack
from fabric.api import put, sudo, warn_only
from cuisine import dir_attribs, mode_sudo


class Deploy(object):
    def __init__(self, project_name='project_name'):
        kwargs = self.get_kwargs()
        self.site = DjangoStack(project_name, **kwargs)

        for checkout in self.get_checkouts():
            self.site.add_checkout(
                checkout['repository'], checkout['destination'], **checkout['kwargs']
            )

        self.site.add_pre_build_hook(self.pre_build)
        self.site.add_post_build_hook(self.post_build)

        for package in self.get_packages():
            self.site.add_additional_package(package)

        for python_dependency in self.get_python_dependencies():
            self.site.add_additional_python_dependency(python_dependency)

        self.site.expose_to_current_module()
        self.site.setup_stack()

    def get_kwargs(self):
        # Return a keyword argument dictionary to pass into the DjangoStack instance.
        raise NotImplementedError('get_kwargs must be implemented')

    def get_checkouts(self):
        # Return a list of dictionaries, each of which contain source_repository,
        # destination and kwargs.
        return []

    def get_packages(self):
        # Return a list of valid system packages to be installed via apt-get.
        return []

    def get_python_dependencies(self):
        # Return a list of valid python dependencies to be installed by pip.
        return []

    def pre_build(self):
        # Whatever needs to be done before DjangoStack deploys.
        return None

    def post_build(self):
        # Whatever needs to be done after DjangoStack deploys.
        return None


class DeployFullStack(Deploy):
    def get_kwargs(self):
        return {
            'web_server': 'nginx',
            'web_server_config_name': 'nginx/nginx.conf',
            'uwsgi_ini_path': '/var/django/project/nginx/uwsgi.ini',
            'uwsgi_params_path': '/var/django/project/nginx/uwsgi_params',
            'scm_type': 'mercurial',
            'database_name': 'name',
            'database_user': 'user',
            'database_password': 'password',
            'database_dump_type': 'SQL',
            'pg_hba_conf_name': 'postgresql/pg_hba.conf',
            'postgresql_conf_name': 'postgresql/postgresql.conf',
            'django_version_number': '1.6.2',
            'django_project_path': '/var/django/project/',
            'django_project_requirements_path': '/var/django/project/requirements.txt',
            'django_static_path': '/var/django/project/static/',
            'django_local_settings_name': 'localsettings.py',
            'django_local_settings_path': '/var/django/project/',
            'make_messages_args': '--ignore=blog/* --ignore=alerts/*',
            'django_locale_path': '/var/django/project/locale/',
            'use_transifex': True,
            'transifexrc_name': '.transifexrc',
        }

    def get_checkouts(self):
        return [
            {
                'repository': 'ssh://hg@bitbucket.org/account/project',
                'destination': '/var/django/project/',
                'kwargs': {
                    'dir_attribs': [
                        {
                            'dir_path': '/var/django/', 'mode': None, 'owner': 'www-data',
                            'group': 'www-data', 'recursive': True
                        },
                        {
                            'dir_path': '/var/django/project/', 'mode': None, 'owner': 'www-data',
                            'group': 'www-data', 'recursive': True
                        }
                    ],
                    'uids': [
                        {
                            'dir_path': '/var/django/project/logs/',
                            'dirs': False, 'files': True
                        }
                    ],
                    'gids': [
                        {'dir_path': '/var/django/project/', 'dirs': True, 'files': True}
                    ]
                }
            }
        ]

    def get_packages(self):
        return ['rabbitmq-server']

    def get_python_dependencies(self):
        return ['python-memcached', 'python-dateutil']

    def post_build(self):
        with mode_sudo():
            # Sets up a new RabbitMQ user and deletes the default guest user
            with warn_only():
                sudo('rabbitmqctl delete_user user')
                sudo('rabbitmqctl delete_user guest')
            sudo('rabbitmqctl add_user user password')
            sudo("rabbitmqctl set_permissions -p / user '.*' '.*' '.*'")

            # Updates PYTHONPATH and performs a south migration - to include djceelry module
            path_1 = ':/var/django/project'
            sudo('export PYTHONPATH=$PYTHONPATH'+path_1)
            if self.site.run_sync_db:
                sudo('cd /var/django/project/ && python manage.py migrate')

            #------------------------------------------------------
            # Celery/Celerybeat Setup

            # Creates and setups up the celery folder for logs and PID files
            # sets the owner as www-data.
            sudo('cd /home/ && mkdir -p celery')
            dir_attribs('/home/celery/', owner='www-data', recursive=True)

            # Set permissions so only www-data can access this folder and its
            # contents.
            sudo('chmod 700 -R /home/celery/')

            # Copy over the daemon and configuration files to the appropriate directories.
            # Make the daemon files executable.
            put('celeryd.init', '/etc/init.d/', use_sudo=True)
            put('celerybeat.init', '/etc/init.d/', use_sudo=True)
            put('celeryd.default', '/etc/default/', use_sudo=True)
            put('celerybeat.default', '/etc/default/', use_sudo=True)
            sudo('cd /etc/init.d/ && mv celeryd.init celeryd && mv celerybeat.init celerybeat')
            sudo(
                'cd /etc/default/ && mv celeryd.default celeryd && '
                'mv celerybeat.default celerybeat'
            )
            sudo('chmod +x /etc/init.d/celeryd')
            sudo('chmod +x /etc/init.d/celerybeat')

            # Start the celeryd daemon with celerybeat (-B).
            sudo('service celeryd start -B')

            # Sets celeryd service to auto start and auto stop on startup/shutdown
            # respectively.
            sudo('update-rc.d celeryd defaults 99 01')
            #------------------------------------------------------


class DeploySCM(Deploy):
    def get_kwargs(self):
        return {
            'scm_type': 'mercurial',
            'deploy_scm': True,
            'deploy_database': False,
            'deploy_django': False,
            'deploy_web_server': False,
            'restore_database': False
        }


class DeployDatabase(Deploy):
    def get_kwargs(self):
        return {
            'database_name': 'name',
            'database_user': 'user',
            'database_password': 'password',
            'database_dump_type': 'SQL',
            'database_dump_name': 'dbdump.txt',
            'pg_hba_conf_name': 'postgresql/pg_hba.conf',
            'postgresql_conf_name': 'postgresql/postgresql.conf',
            'deploy_scm': False,
            'deploy_database': True,
            'deploy_django': False,
            'deploy_web_server': False,
            'restore_database': True
        }


class DeployDjango(DeployFullStack):
    def get_kwargs(self):
        return {
            'django_version_number': '1.6.2',
            'django_project_path': '/var/django/project/',
            'django_project_requirements_path': '/var/django/project/requirements.txt',
            'django_static_path': '/var/django/project/static/',
            'django_local_settings_name': 'localsettings.py',
            'django_local_settings_path': '/var/django/project/',
            'make_messages_args': '--ignore=blog/* --ignore=alerts/*',
            'django_locale_path': '/var/django/project/locale/',
            'use_transifex': True,
            'transifexrc_name': '.transifexrc',
            'deploy_scm': False,
            'deploy_database': False,
            'deploy_django': True,
            'deploy_web_server': False,
            'restore_database': False
        }


class DeployWebServer(Deploy):
    def get_kwargs(self):
        return {
            'web_server': 'nginx',
            'web_server_config_name': 'nginx/nginx.conf',
            'uwsgi_ini_path': '/var/django/project/nginx/uwsgi.ini',
            'uwsgi_params_path': '/var/django/project/nginx/uwsgi_params',
            'deploy_scm': False,
            'deploy_database': False,
            'deploy_django': False,
            'deploy_web_server': True,
            'restore_database': False
        }
