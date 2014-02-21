import time

from taskset import TaskSet, task_method
from fabric.api import *
from fabric.contrib.files import exists
from cuisine import *
from cuisine_postgresql import postgresql_role_ensure, \
    postgresql_database_ensure


class DjangoStack(TaskSet):
    WEB_SERVERS = ['apache', 'nginx']
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
    django_project_path = None  # Where the django project will be pulled to
    django_project_requirements_path = None  # Where the django project's requirements file resides
    django_static_path = None  # Path to static dir if django static files are served locally
    django_local_settings_name = None  # If given, an un-tracked local settings file name
    django_local_settings_path = None  # If given, the path to place the local settings file
    #  Default django superuser details
    default_django_admin_user = 'admin'
    default_django_admin_password = 'notagoodpassword'
    default_django_admin_email = 'admin@example.com'
    django_version_number = ''  # If not specified the latest version will be installed

    def __init__(self, project_name, **kwargs):
        self.project_name = project_name
        self.python_dependencies = self.default_python_dependencies
        self.web_server = kwargs.get('web_server', self.web_server)
        if self.web_server not in self.WEB_SERVERS:
            raise InvalidKwargsException(
                '%s is not a valid web_server. Options are: %s' %
                (self.web_server, self.WEB_SERVERS)
            )
        self.web_server_config_name = \
            kwargs.get('web_server_config_name', self.web_server_config_name)
        self.uwsgi_ini_name = kwargs.get('uwsgi_ini_name', self.uwsgi_ini_name)
        self.uwsgi_ini_path = kwargs.get('uwsgi_ini_path', self.uwsgi_ini_path)
        self.uwsgi_params_name = kwargs.get('uwsgi_params_name', self.uwsgi_params_name)
        self.uwsgi_params_path = kwargs.get('uwsgi_params_path', self.uwsgi_params_path)
        if self.web_server == 'nginx' and (not self.uwsgi_ini_path or not self.uwsgi_params_path):
            raise InvalidKwargsException(
                'uwsgi_ini_path and uwsgi_params_path must be specified if web_server is '
                'set to nginx. You can set uwsgi_ini_name and uwsgi_params_name to None '
                '(default) if you know these files will exist on the server or in a cloned '
                'repository.'
            )
        self.scm_type = kwargs.get('scm_type', self.scm_type)
        self.database_name = kwargs.get('database_name', self.database_name)
        self.database_user = kwargs.get('database_user', self.database_user)
        self.database_password = kwargs.get('database_password', self.database_password)
        self.database_dump_type = kwargs.get('database_dump_type', self.database_dump_type)
        self.django_project_path = kwargs.get('django_project_path', self.django_project_path)
        self.django_project_requirements_path = \
            kwargs.get('django_project_requirements_path', self.django_project_requirements_path)
        self.django_static_path = kwargs.get('django_static_path', self.django_static_path)
        self.django_local_settings_name = \
            kwargs.get('django_local_settings_name', self.django_local_settings_name)
        self.django_local_settings_path = \
            kwargs.get('django_local_settings_path', self.django_local_settings_path)
        self.default_django_admin_user = \
            kwargs.get('default_django_admin_user', self.default_django_admin_user)
        self.default_django_admin_password = \
            kwargs.get('default_django_admin_password', self.default_django_admin_password)
        self.default_django_admin_email = \
            kwargs.get('default_django_admin_email', self.default_django_admin_email)
        self.django_version_number = \
            kwargs.get('django_version_number', self.django_version_number)
        if self.django_version_number != '':
            self.python_dependencies.append('django==%s' % self.django_version_number)
        else:
            self.python_dependencies.append('django')
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

    def add_checkout(self, source_repository, destination):
        self.repositories.append([source_repository, destination])

    def add_pre_build_hook(self, func):
        self.pre_build_hooks.append(func)

    def add_post_build_hook(self, func):
        self.post_build_hooks.append(func)

    @task_method(default=True)
    def setup_stack(self):
        package_update()

        self.run_pre_build_hooks()

        self.setup_scm()
        self.setup_postgres()
        self.setup_additional_packages()
        self.setup_python()

        if self.web_server == 'apache':
            self.setup_apache()
        elif self.web_server == 'nginx':
            self.setup_nginx()

        self.create_database_user()
        self.create_database()

        self.setup_bitbucket_key()
        self.checkout_code()

        self.install_django_project_requirements()
        self.setup_web_server()

        self.restore_database_dump()
        self.syncdb()
        self.collect_static()
        self.move_local_settings_file()

        self.run_post_build_hooks()

        self.restart_services()

    @task_method
    def run_pre_build_hooks(self):
        for hook in self.pre_build_hooks:
            hook()

    @task_method
    def setup_scm(self):
        if self.scm_type == 'mercurial':
            package_ensure('mercurial')
        elif self.scm_type.lower() == 'git':
            package_ensure('git')

    @task_method
    def setup_postgres(self):
        package_ensure('postgresql')
        package_ensure('postgresql-client')
        package_ensure('libpq-dev')

    @task_method
    def setup_additional_packages(self):
        for package_name in self.packages:
            package_ensure(package_name)

    @task_method
    def setup_python(self):
        package_ensure('build-essential')
        package_ensure('python')
        package_ensure('python-dev')
        package_ensure('python-pip')

        for dependency in self.python_dependencies:
            sudo('pip install %s' % dependency)

    @task_method
    def setup_apache(self, destroy_nginx=True):
        if destroy_nginx:
            with mode_sudo():
                with warn_only():
                    run('service nginx stop')
                run('apt-get -y purge nginx')
                run('apt-get -y autoremove')
                run('/usr/bin/yes | sudo pip uninstall uwsgi')

        had_apache = package_ensure('apache2')
        package_ensure('libapache2-mod-python')
        package_ensure('libapache2-mod-wsgi')
        sudo('a2enmod rewrite')

        if not had_apache and hasattr(env, 'vagrant_mode'):
            local('vagrant reload')
            time.sleep(15)

    @task_method
    def setup_nginx(self, destroy_apache=True):
        if destroy_apache:
            with mode_sudo():
                with warn_only():
                    run('service apache2 stop')
                run('apt-get -y purge apache2 apache2-utils apache2.2-bin apache2-common')
                run('apt-get -y autoremove')

        package_ensure('nginx')
        sudo('pip install uwsgi')

    @task_method
    def create_database_user(self):
        postgresql_role_ensure(self.database_user, self.database_password, createdb=True)

    @task_method
    def create_database(self):
        postgresql_database_ensure(
            self.database_name,
            owner=self.database_user,
            encoding='utf8',
            template='template0',
            locale='en_US.UTF-8'
        )

    @task_method
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

    @task_method
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
        for source_repository, destination in self.repositories:
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

    @task_method
    def install_django_project_requirements(self):
        if self.django_project_requirements_path:
            with mode_sudo():
                run('pip install -r %s' % self.django_project_requirements_path)

    @task_method
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

    @task_method
    def restore_database_dump(self):
        with mode_sudo():
            if not exists('/var/lib/postgresql/dbdump.txt'):
                put('dbdump.txt', '/var/lib/postgresql/', use_sudo=True)
            run('chown postgres /var/lib/postgresql/dbdump.txt')

            if self.database_dump_type == 'SQL':
                run(
                    'cd /var/lib/postgresql;'
                    'psql %s < dbdump.txt' % self.database_name, user='postgres'
                )
            else:
                run(
                    'cd /var/lib/postgresql;'
                    'pg_restore -d %s dbdump.txt' % self.database_name,
                    user='postgres'
                )

    @task_method
    def syncdb(self):
        if self.django_project_path:
            sudo(
                'cd %s;python manage.py syncdb --noinput;'
                'python manage.py migrate --noinput;' % self.django_project_path
            )

    @task_method
    def collect_static(self):
        if self.django_project_path:
            with mode_sudo():
                if self.django_static_path:
                    run('mkdir -p %s' % self.django_static_path)
                run('cd %s;python manage.py collectstatic --noinput' % self.django_project_path)

    @task_method
    def move_local_settings_file(self):
        if self.django_local_settings_name and self.django_local_settings_path:
            put(
                self.django_local_settings_name, self.django_local_settings_path,
                use_sudo=True
            )

    @task_method
    def run_post_build_hooks(self):
        for hook in self.post_build_hooks:
            hook()

    @task_method
    def restart_services(self):
        with mode_sudo():
            if self.web_server == 'apache':
                run('service apache2 restart', pty=False)
            elif self.web_server == 'nginx':
                run('service nginx restart')
                run('uwsgi --ini %s' % self.uwsgi_ini_path)
            run('service postgresql restart')

    @task_method
    def use_vagrant(self):
        env.user = 'vagrant'
        env.hosts = ['127.0.0.1:2222']
        env.vagrant_mode = True

        # retrieve the IdentityFile:
        result = local('vagrant ssh-config | grep IdentityFile', capture=True)
        env.key_filename = result.split()[1][1:-1]  # parse IdentityFile

    @task_method
    def create_django_admin_user(self):
        # TODO: make this idempotent:
        if self.django_project_path:
            sudo(
                "cd %s;echo \"from django.contrib.auth.models import User;"
                "User.objects.create_superuser('%s', '%s', '%s')\" | ./manage.py shell" % (
                    self.django_project_path,
                    self.default_django_admin_user,
                    self.default_django_admin_email,
                    self.default_django_admin_password
                )
            )


class InvalidKwargsException(Exception):
    pass
