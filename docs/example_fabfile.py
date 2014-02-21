from djangostack import DjangoStack
from fabric.api import put, sudo
from cuisine import dir_attribs, mode_sudo

# Apache setup (DjangoStack default)
kwargs = {
    'web_server_config_name': 'apache/apache.conf',
    'scm_type': 'mercurial',
    'database_name': 'name',
    'database_user': 'user',
    'database_password': 'password',
    'database_dump_type': 'SQL',
    'django_version_number': '1.6.2',
    'django_project_path': '/var/django/project/django_dir/',
    'django_project_requirements_path': '/var/django/project/django_dir/requirements.txt',
    'django_static_path': '/var/django/project/django_dir/static/',
    'django_local_settings_name': 'localsettings.py',
    'django_local_settings_path': '/var/django/project/django_dir/',
    'django_locale_path': '/var/django/project/django_dir/locale/',
    'use_transifex': True,
    'transifexrc_name': '.transifexrc'
}

# Nginx/uwsgi setup without uwsgi_ini_name/uwsgi_params_name set
# kwargs = {
#     'web_server': 'nginx',
#     'web_server_config_name': 'nginx/nginx.conf',
#     'uwsgi_ini_path': '/var/django/project/django_dir/nginx/uwsgi.ini',
#     'uwsgi_params_path': '/var/django/project/django_dir/nginx/uwsgi_params',
#     'scm_type': 'mercurial',
#     'database_name': 'name',
#     'database_user': 'user',
#     'database_password': 'password',
#     'database_dump_type': 'SQL',
#     'django_version_number': '1.6.2',
#     'django_project_path': '/var/django/project/django_dir/',
#     'django_project_requirements_path': '/var/django/project/django_dir/requirements.txt',
#     'django_static_path': '/var/django/project/django_dir/static/',
#     'django_local_settings_name': 'localsettings.py',
#     'django_local_settings_path': '/var/django/project/django_dir/',
#     'django_locale_path': '/var/django/project/django_dir/locale/',
#     'use_transifex': True,
#     'transifexrc_name': '.transifexrc'
# }

# Nginx/uwsgi setup with uwsgi_ini_name/uwsgi_params_name set
# kwargs = {
#     'web_server': 'nginx',
#     'web_server_config_name': 'nginx/nginx.conf',
#     'uwsgi_ini_name': 'nginx/uwsgi.ini',
#     'uwsgi_ini_path': '/var/django/project/django_dir/nginx/uwsgi.ini',
#     'uwsgi_params_name': 'nginx/uwsgi_params',
#     'uwsgi_params_path': '/var/django/project/django_dir/nginx/uwsgi_params',
#     'scm_type': 'mercurial',
#     'database_name': 'name',
#     'database_user': 'user',
#     'database_password': 'password',
#     'database_dump_type': 'SQL',
#     'django_version_number': '1.6.2',
#     'django_project_path': '/var/django/project/django_dir/',
#     'django_project_requirements_path': '/var/django/project/django_dir/requirements.txt',
#     'django_static_path': '/var/django/project/django_dir/static/',
#     'django_local_settings_name': 'localsettings.py',
#     'django_local_settings_path': '/var/django/project/django_dir/',
#     'django_locale_path': '/var/django/project/django_dir/locale/',
#     'use_transifex': True,
#     'transifexrc_name': '.transifexrc'
# }

# SCM deployment only
# kwargs = {
#     'deploy_scm': True,
#     'deploy_database': False,
#     'deploy_django': False,
#     'deploy_web_server': False
# }

# Database deployment only
# kwargs = {
#     'deploy_scm': False,
#     'deploy_database': True,
#     'deploy_django': False,
#     'deploy_web_server': False
# }

# Django deployment only
# kwargs = {
#     'deploy_scm': False,
#     'deploy_database': False,
#     'deploy_django': True,
#     'deploy_web_server': False
# }

# Web Server deployment only
# kwargs = {
#     'deploy_scm': False,
#     'deploy_database': False,
#     'deploy_django': False,
#     'deploy_web_server': True
# }

site = DjangoStack('project_name', **kwargs)
site.add_checkout('ssh://hg@bitbucket.org/account/project', '/var/django/project/')


def pre_build():
    pass  # To pre build stuff here


def post_build():
    pass  # To post build stuff here.


site.add_pre_build_hook(pre_build)
site.add_post_build_hook(post_build)
site.add_additional_package('rabbitmq-server')
site.add_additional_python_dependency('python-memcached')
site.add_additional_python_dependency('python-dateutil')
site.expose_to_current_module()
