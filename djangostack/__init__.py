import time
import datetime

from taskset import TaskSet, task_method
from fabric.api import *
from fabric.contrib.files import exists, append, contains
from cuisine import *
from cuisine_postgresql import postgresql_role_ensure, \
    postgresql_database_ensure


class DjangoStack(TaskSet):
    deploy_scm = True  # Deploy SCM
    deploy_database = True  # Deploy Database
    deploy_django = True  # Deploy Django
    deploy_web_server = True  # Deploy Web Server
    restore_database = True  # Restore Database
    WEB_SERVERS = ['apache', 'nginx']
    SCM_TYPES = ['mercurial', 'git']
    default_additional_packages = ['vim', 'gettext']  # System packages to install
    # Python packages to install
    default_python_dependencies = ['psycopg2', 'south']
    web_server = 'apache'  # Web server to install
    web_server_config_name = 'web_server_config'  # Local web server config file name
    uwsgi_ini_name = None  # Local uwsgi.ini file name (nginx only)
    uwsgi_ini_path = None  # Path to copy uwsgi.ini file to (nginx only)
    uwsgi_params_name = None  # Local uwsgi_params file name (nginx only)
    uwsgi_params_path = None  # Path to copy uwsgi_params file to (nginx only)
    scm_type = 'mercurial'  # Version control to use
    database_name = None  # Database name to create
    database_user = None  # Database user to create
    database_password = None  # Database user password
    database_dump_type = 'SQL'  # Database dump type
    database_dump_name = 'dbdump.txt'  # Local database dump file
    pg_hba_conf_name = None
    postgresql_conf_name = None
    django_project_path = None  # Where the django project will be pulled to
    django_project_requirements_path = None  # Where the django project's requirements file resides
    django_static_path = None  # Path to static dir if django static files are served locally
    django_local_settings_name = None  # If given, an un-tracked local settings file name
    django_local_settings_path = None  # If given, the path to place the local settings file
    django_version_number = ''  # If not specified the latest version will be installed
    run_sync_db = True  # It might be required to deploy a django project but not sync the database
    make_messages_args = ''  # Additional arguments to the django makemessages command.
    django_locale_path = None  # Django locale directory path
    # Use transifex to force pull updated translations before making and compiling translations -
    # django_locale_path must contain a .tx directory which contains the transifex config file
    use_transifex = False
    transifexrc_name = None  # Local .transifexrc file name

    def __init__(self, project_name, **kwargs):
        self.project_name = project_name
        self.deploy_scm = kwargs.get('deploy_scm', self.deploy_scm)
        self.deploy_database = kwargs.get('deploy_database', self.deploy_database)
        if not self.deploy_database:
            self.default_python_dependencies.remove('psycopg2')
        self.deploy_django = kwargs.get('deploy_django', self.deploy_django)
        self.deploy_web_server = kwargs.get('deploy_web_server', self.deploy_web_server)
        if not self.deploy_web_server:
            self.default_python_dependencies.remove('south')
        self.restore_database = kwargs.get('restore_database', self.restore_database)
        self.python_dependencies = self.default_python_dependencies
        self.web_server = kwargs.get('web_server', self.web_server)
        if self.deploy_web_server and self.web_server not in self.WEB_SERVERS:
            raise InvalidArgumentException(
                '%s is not a valid web_server. Options are: %s' %
                (self.web_server, self.WEB_SERVERS)
            )
        self.web_server_config_name = \
            kwargs.get('web_server_config_name', self.web_server_config_name)
        self.uwsgi_ini_name = kwargs.get('uwsgi_ini_name', self.uwsgi_ini_name)
        self.uwsgi_ini_path = kwargs.get('uwsgi_ini_path', self.uwsgi_ini_path)
        self.uwsgi_params_name = kwargs.get('uwsgi_params_name', self.uwsgi_params_name)
        self.uwsgi_params_path = kwargs.get('uwsgi_params_path', self.uwsgi_params_path)
        if self.deploy_web_server and self.web_server == 'nginx' and \
                (not self.uwsgi_ini_path or not self.uwsgi_params_path):
            raise InvalidArgumentException(
                'uwsgi_ini_path and uwsgi_params_path must be specified if web_server is '
                'set to nginx. You can set uwsgi_ini_name and uwsgi_params_name to None '
                '(default) if you know these files will exist on the server or in a cloned '
                'repository.'
            )
        self.scm_type = kwargs.get('scm_type', self.scm_type)
        if self.scm_type not in self.SCM_TYPES:
            raise InvalidArgumentException(
                '%s is not a valid scm_type. Options are: %s' %
                (self.scm_type, self.SCM_TYPES)
            )
        self.database_name = kwargs.get('database_name', self.database_name)
        self.database_user = kwargs.get('database_user', self.database_user)
        self.database_password = kwargs.get('database_password', self.database_password)
        if self.deploy_database and \
                (not self.database_name or not self.database_user or not self.database_password):
            raise InvalidArgumentException(
                'database_name, database_user and database_password must be '
                'specified if deploy_database is True.'
            )
        self.database_dump_type = kwargs.get('database_dump_type', self.database_dump_type)
        self.database_dump_name = kwargs.get('database_dump_name', self.database_dump_name)
        self.pg_hba_conf_name = kwargs.get('pg_hba_conf_name', self.pg_hba_conf_name)
        self.postgresql_conf_name = kwargs.get('postgresql_conf_name', self.postgresql_conf_name)
        self.django_project_path = kwargs.get('django_project_path', self.django_project_path)
        self.django_project_requirements_path = \
            kwargs.get('django_project_requirements_path', self.django_project_requirements_path)
        self.django_static_path = kwargs.get('django_static_path', self.django_static_path)
        self.django_local_settings_name = \
            kwargs.get('django_local_settings_name', self.django_local_settings_name)
        self.django_local_settings_path = \
            kwargs.get('django_local_settings_path', self.django_local_settings_path)
        self.django_version_number = \
            kwargs.get('django_version_number', self.django_version_number)
        self.run_sync_db = kwargs.get('run_sync_db', self.run_sync_db)
        self.make_messages_args = kwargs.get('make_messages_args', self.make_messages_args)
        self.django_locale_path = kwargs.get('django_locale_path', self.django_locale_path)
        self.use_transifex = kwargs.get('use_transifex', self.use_transifex)
        self.transifexrc_name = kwargs.get('transifexrc_name', self.transifexrc_name)
        if self.deploy_django:
            if self.django_version_number != '':
                self.python_dependencies.append('django==%s' % self.django_version_number)
            else:
                self.python_dependencies.append('django')

            if self.use_transifex:
                if not self.transifexrc_name or not self.django_locale_path:
                    raise InvalidArgumentException(
                        'transifex_name and django_locale_path must be '
                        'specified if use_transifex is True.'
                    )
                self.python_dependencies.append('transifex-client')
        self.repositories = []
        self.packages = []
        self.packages.extend(self.default_additional_packages)
        self.pre_build_hooks = []
        self.post_build_hooks = []

        # check for deploy key file
        # check for apache config file

    def add_additional_python_dependency(self, dependency):
        self.python_dependencies.append(dependency)

    def add_additional_package(self, package_name):
        self.packages.append(package_name)

    def add_checkout(self, source_repository, destination, **kwargs):
        self.repositories.append([source_repository, destination, kwargs])

    def add_pre_build_hook(self, func):
        self.pre_build_hooks.append(func)

    def add_post_build_hook(self, func):
        self.post_build_hooks.append(func)

    def set_dir_attribs(self, dir_path, mode=None, owner=None, group=None, recursive=True):
        with mode_sudo():
            dir_attribs(dir_path, mode=mode, owner=owner, group=group, recursive=recursive)

    def set_uid(self, dir_path, dirs=True, files=True):
        if dirs:
            sudo("find %s -type d -exec chmod u+s '{}' \;" % dir_path)
        if files:
            sudo("find %s -type f -exec chmod u+s '{}' \;" % dir_path)

    def set_gid(self, dir_path, dirs=True, files=True):
        if dirs:
            sudo("find %s -type d -exec chmod g+s '{}' \;" % dir_path)
        if files:
            sudo("find %s -type f -exec chmod g+s '{}' \;" % dir_path)

    def _validate_boolean_input(self, input):
        if input not in ['y', 'Y', 'n', 'N']:
            raise InvalidArgumentException('Please enter y (yes) or n (no).')
        return input

    def _pre_build(self):
        with mode_sudo():
            if exists('~/.djangostack'):
                print('\nIt appears that DjangoStack has been deployed to this server before:')
                run('cat ~/.djangostack')
                deploy = prompt(
                    'Are you sure you wish to continue? [y/n]',
                    validate=self._validate_boolean_input
                )
                if deploy.lower() == 'y':
                    run('rm ~/.djangostack')
                else:
                    abort('DjangoStack deployment aborted.')

    def _post_build(self):
        now = datetime.datetime.now()
        sudo('touch ~/.djangostack')
        append(
            '~/.djangostack',
            [
                'Deployed on: %s at %s' % (now.strftime('%d/%m/%Y'), now.strftime('%H:%M:%S')),
                'SCM Deployed: %s' % self.deploy_scm,
                'Database Deployed: %s' % self.deploy_database,
                'Django Deployed: %s' % self.deploy_django,
                'Web Server Deployed: %s' % self.deploy_web_server,
                'Database Restored: %s' % self.restore_database
            ],
            use_sudo=True
        )

    def _update_repository_permissions(self):
        for source_repository, destination, kwargs in self.repositories:
            dir_attribs = kwargs.get('dir_attribs')
            uids = kwargs.get('uids')
            gids = kwargs.get('gids')

            for item in dir_attribs:
                self.set_dir_attribs(item['dir_path'], item['mode'], item['owner'], item['group'])

            for item in uids:
                self.set_uid(item['dir_path'], item.get('dirs', True), item.get('files', True))

            for item in gids:
                self.set_gid(item['dir_path'], item.get('dirs', True), item.get('files', True))

    @task_method(default=True)
    def setup_stack(self):
        self._pre_build()

        package_update()

        self.run_pre_build_hooks()

        if self.deploy_scm or self.repositories:
            self.setup_scm()

        if self.deploy_database:
            self.setup_postgres()

        self.setup_additional_packages()
        self.setup_python()

        if self.deploy_web_server:
            if self.web_server == 'apache':
                self.setup_apache()
            elif self.web_server == 'nginx':
                self.setup_nginx()

        if self.deploy_database:
            self.create_database_user()
            self.create_database()

        if self.deploy_scm or self.repositories:
            self.setup_bitbucket_key()
            self.checkout_code()

        if self.deploy_django:
            self.install_django_project_requirements()

        if self.deploy_web_server:
            self.setup_web_server()

        if self.deploy_database:
            self.restore_database_configuration()
            if self.restore_database:
                self.restore_database_dump()

        if self.deploy_django:
            self.syncdb()
            self.collect_static()
            self.move_local_settings_file()
            self.make_and_compile_messages(use_transifex=self.use_transifex)

        self.run_post_build_hooks()
        self._update_repository_permissions()
        self.restart_services()
        self._post_build()

    def run_pre_build_hooks(self):
        for hook in self.pre_build_hooks:
            hook()

    def setup_scm(self):
        if self.scm_type == 'mercurial':
            package_ensure('mercurial')
        elif self.scm_type.lower() == 'git':
            package_ensure('git')

    def setup_postgres(self):
        package_ensure('postgresql')
        package_ensure('postgresql-client')
        package_ensure('libpq-dev')

    def setup_additional_packages(self):
        for package_name in self.packages:
            package_ensure(package_name)

    def setup_python(self):
        package_ensure('build-essential')
        package_ensure('python')
        package_ensure('python-dev')
        package_ensure('python-pip')

        for dependency in self.python_dependencies:
            sudo('pip install %s' % dependency)

    def setup_apache(self, destroy_nginx=True):
        if destroy_nginx:
            with mode_sudo():
                with warn_only():
                    run('service nginx stop')
                    run('/usr/bin/yes | sudo pip uninstall uwsgi')
                run('apt-get -y purge nginx nginx-common')
                run('apt-get -y autoremove')

        had_apache = package_ensure('apache2')
        package_ensure('libapache2-mod-python')
        package_ensure('libapache2-mod-wsgi')
        sudo('a2enmod rewrite')

        if not had_apache and hasattr(env, 'vagrant_mode'):
            local('vagrant reload')
            time.sleep(15)

    def setup_nginx(self, destroy_apache=True):
        if destroy_apache:
            with mode_sudo():
                with warn_only():
                    run('service apache2 stop')
                run('apt-get -y purge apache2 apache2-utils apache2.2-bin apache2-common')
                run('apt-get -y autoremove')

        package_ensure('nginx')
        sudo('pip install uwsgi')

    def create_database_user(self):
        postgresql_role_ensure(self.database_user, self.database_password, createdb=True)

    def create_database(self):
        postgresql_database_ensure(
            self.database_name,
            owner=self.database_user,
            encoding='utf8',
            template='template0',
            locale='en_US.UTF-8'
        )

    def setup_bitbucket_key(self):
        with mode_sudo():
            dir_ensure('/root/.ssh/')
        put('deploykey', '~/id_rsa')
        put('deploykey.pub', '~/id_rsa.pub')
        bitbuckethost = 'bitbucket.org ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAu' \
            'biN81eDcafrgMeLzaFPsw2kNvEcqTKl/VqLat/MaB33pZy0y3rJZtnqwR2qOOvb' \
            'wKZYKiEO1O6VqNEBxKvJJelCq0dTXWT5pbO2gDXC6h6QDXCaHo6pOHGPUy+YBaG' \
            'QRGuSusMEASYiWunYN0vCAI8QaXnWMXNMdFP3jHAJH0eDsoiGnLPBlBp4TNm6rY' \
            'I74nMzgz3B9IikW4WVK+dc8KZJZWYjAuORU3jc1c/NPskD2ASinf8v3xnfXeukU' \
            '0sJ5N6m5E8VLjObPEO+mN2t/FZTMZLiFqPWc/ALSqnMnnhwrNi2rbfg/rd/IpL8' \
            'Le3pSBne8+seeFVBoGqzHM9yXw=='
        with mode_sudo():
            run('mv ~/id_rsa /root/.ssh/')
            run('mv ~/id_rsa.pub /root/.ssh/')
            run("echo '%s' >> /root/.ssh/known_hosts" % bitbuckethost)

    def checkout_code(self):
        scm_command = scm_dir = scm_ignore = None
        if self.scm_type.lower() == 'mercurial':
            scm_command = 'hg clone'
            scm_dir = '.hg'
            scm_ignore = '.hgignore'
        elif self.scm_type.lower() == 'git':
            scm_command = 'git clone'
            scm_dir = '.git'
            scm_ignore = '.gitignore'

        run('rm -fr /tmp/%s/' % self.project_name)
        for source_repository, destination, kwargs in self.repositories:
            with mode_sudo():
                run('rm -fr %s*' % destination)
                run('rm -fr %s%s' % (destination, scm_dir))
                run('rm -fr %s%s' % (destination, scm_ignore))
                run('%s %s %s' % (scm_command, source_repository, '/tmp/%s/' % self.project_name))
                run('mkdir -p %s' % destination)
                run('cp -R /tmp/%s/* %s' % (self.project_name, destination))
                run('cp -R /tmp/%s/%s %s' % (self.project_name, scm_dir, destination))
                run('cp /tmp/%s/%s %s' % (self.project_name, scm_ignore, destination))
                run('rm -fr /tmp/%s/' % self.project_name)

    def install_django_project_requirements(self):
        if self.django_project_requirements_path:
            if not self.deploy_database:
                # Ensures dependencies are installed if deploy_database is False
                # and psycopg2 exists in the requirements file.
                if contains(self.django_project_requirements_path, 'psycopg2', use_sudo=True):
                    package_ensure('python-psycopg2')
            sudo('pip install -r %s' % self.django_project_requirements_path)

    def setup_web_server(self):
        if self.web_server == 'apache':
            with mode_sudo():
                run('rm -f /etc/apache2/sites-enabled/000-default')
                run('rm -f /etc/apache2/sites-enabled/%s' % self.project_name)
                run('rm -f /etc/apache2/sites-available/%s' % self.project_name)

                put(
                    '%s' % self.web_server_config_name,
                    '/etc/apache2/sites-available/%s' % self.project_name, use_sudo=True
                )
                run(
                    'ln -s /etc/apache2/sites-available/%s /etc/apache2/sites-enabled/%s' %
                    (self.project_name, self.project_name)
                )
        elif self.web_server == 'nginx':
            with mode_sudo():
                run('rm -f /etc/nginx/sites-enabled/default')
                run('rm -f /etc/nginx/sites-enabled/%s' % self.project_name)
                run('rm -f /etc/nginx/sites-available/%s' % self.project_name)

                put(
                    '%s' % self.web_server_config_name,
                    '/etc/nginx/sites-available/%s' % self.project_name, use_sudo=True
                )
                run(
                    'ln -s /etc/nginx/sites-available/%s /etc/nginx/sites-enabled/%s' %
                    (self.project_name, self.project_name)
                )

                if self.uwsgi_ini_name:
                    put('%s' % self.uwsgi_ini_name, '%s' % self.uwsgi_ini_path, use_sudo=True)
                if self.uwsgi_params_name:
                    put(
                        '%s' % self.uwsgi_params_name, '%s' % self.uwsgi_params_path, use_sudo=True
                    )

    def restore_database_configuration(self):
        with mode_sudo():
            if self.pg_hba_conf_name:
                file_path = run("find /etc/postgresql -name 'pg_hba.conf'")
                if file_path:
                    put(self.pg_hba_conf_name, file_path, use_sudo=True)
                    run('chown postgres:postgres %s' % file_path)
            if self.postgresql_conf_name:
                file_path = run("find /etc/postgresql -name 'postgresql.conf'")
                if file_path:
                    put(self.postgresql_conf_name, file_path, use_sudo=True)
                    run('chown postgres:postgres %s' % file_path)

    def restore_database_dump(self):
        with mode_sudo():
            if not exists('/var/lib/postgresql/%s' % self.database_dump_name):
                put(self.database_dump_name, '/var/lib/postgresql/', use_sudo=True)
            run('chown postgres /var/lib/postgresql/%s' % self.database_dump_name)

            if self.database_dump_type == 'SQL':
                run(
                    'cd /var/lib/postgresql;'
                    'psql %s < %s' % (self.database_name, self.database_dump_name), user='postgres'
                )
            else:
                run(
                    'cd /var/lib/postgresql;'
                    'pg_restore -d %s %s' % (self.database_name, self.database_dump_name),
                    user='postgres'
                )

    def syncdb(self):
        if self.django_project_path and self.run_sync_db:
            sudo(
                'cd %s;python manage.py syncdb --noinput;'
                'python manage.py migrate --noinput;' % self.django_project_path
            )

    def collect_static(self):
        if self.django_project_path:
            with mode_sudo():
                if self.django_static_path:
                    run('mkdir -p %s' % self.django_static_path)
                run('cd %s;python manage.py collectstatic --noinput' % self.django_project_path)

    def move_local_settings_file(self):
        if self.django_local_settings_name and self.django_local_settings_path:
            put(
                self.django_local_settings_name, self.django_local_settings_path,
                use_sudo=True
            )

    def make_and_compile_messages(self, use_transifex=False):
        if use_transifex and self.django_locale_path:
            put(self.transifexrc_name, '~/', use_sudo=True)
            if dir_exists('%s.tx' % self.django_locale_path):
                sudo('cd %s;tx pull -f' % self.django_locale_path)
            else:
                warn(
                    'Could not find .tx directory in the locale directory. '
                    'Could not pull transifex files.'
                )
        if self.django_project_path:
            with mode_sudo():
                run(
                    'cd %s;python manage.py makemessages -a %s' %
                    (self.django_project_path, self.make_messages_args)
                )
                run(
                    'cd %s;python manage.py makemessages -a -d djangojs %s' %
                    (self.django_project_path, self.make_messages_args)
                )
                run('cd %s;python manage.py compilemessages' % self.django_project_path)

    def run_post_build_hooks(self):
        for hook in self.post_build_hooks:
            hook()

    def restart_services(self):
        with mode_sudo():
            if self.deploy_web_server:
                if self.web_server == 'apache':
                    run('service apache2 restart', pty=False)
                elif self.web_server == 'nginx':
                    run('service nginx restart')
                    run('uwsgi --ini %s' % self.uwsgi_ini_path)
            if self.deploy_database:
                run('service postgresql restart')


class InvalidArgumentException(Exception):
    pass
