DjangoStack
-----------

## Deploys the Django Stack to a remote server (Linux, Apache/Nginx, Postgresql, Mercurial/Git)

### DjangoStack Required Arguments
 - **project_name**: The name of the project to be deployed

### DjangoStack Optional Arguments
 - **deploy_scm**: Deploy version control to the deployed server (default: True)
 - **deploy_database**: Deploy database to the deployed server (default: True)
 - **deploy_django**: Deploy Django to the deployed server (default: True)
 - **deploy_web_server**: Deploy Web Server to the deployed server (default: True)
 - **restore_database**: Restore database on the deployed server (default: True) Note deploy_database must be True if this argument is True
 - **web_server**: The type of web server to use (default: apache) Options: ['apache', 'nginx']
 - **web_server_config_name**: The name of the local web server configuration file that will be copied to the deployed server (default: web_server_config)
 - **uwsgi_ini_name**: The name of the local web server uwsgi.ini file that will be copied to the deployed server (default: None) Optionally specified if web_server = nginx
 - **uwsgi_ini_path**: The path to the uwsgi.ini file on the deployed server (default: None) Note this must be specified if web_server = nginx
 - **uwsgi_params_name**: The name of the local web server uwsgi_params file that will be copied to the deployed server (default: None) Optionally specified if web_server = nginx
 - **uwsgi_params_path**: The path to the uwsgi_params file on the deployed server (default: None) Note this must be specified if web_server = nginx
 - **scm_type**: The type of SCM to use (default: mercurial) Options: ['mercurial', 'git']
 - **database_name**: The name of the database to create (default: None) Note this must be specified if deploy_database is True
 - **database_user**: The user to create for the database (default: None) Note this must be specified if deploy_database is True
 - **database_password**: The database password (default: None) Note this must be specified if deploy_database is True
 - **database_dump_type**: The type of database dump to restore (default: SQL)
 - **database_dump_name**: The name of the local database dump file that will be copied to the deployed server (default: dbdump.txt) Ignored if restore_database is False
 - **pg_hba_conf_name**: The name of the local pg_hba.conf file that will be copied to the deployed server and replace the default version (default: None)
 - **postgresql_conf_name**: The name of the local postgresql.conf file that will be copied to the deployed server and replace the default version (default: None)
 - **django_project_path**: The path of the Django project on the deployed server (default: None) Note that the syncdb, collect_static and make_and_compile messages functions depend on this argument being set, otherwise they will not run
 - **django_project_requirements_path**: The path of the Django project's pip requirements file on the deployed server (default: None)
 - **django_static_path**: The path of the Django project's static directory (default: None) Only required if static files are being served by the local server, collectstatic will be run regardless
 - **django_local_settings_name**: The name of the local Django project's local_settings file that will be copied to the deployed server (default: None) Note django_local_settings_name and django_local_settings_path must be set for this to work, otherwise it will fail silently
 - **django_local_settings_path**: The path of the local_settings file on the deployed server, django_local_settings_name will be copied to this location (default: None) Note django_local_settings_name and django_local_settings_path must be set for this to work, otherwise it will fail silently
 - **django_version_number**: The Django version number to deploy (default: '') Note leaving this as the default will deploy the latest stable release version
 - **run_sync_db**: Run Django syncdb and migrate (default: True)
 - **make_messages_args**: Additional arguments (as a string) to pass to the Django makemessages command
 - **django_locale_path**: The path of the Django project's locale directory on the deployed server (default: None) Only required if use_transifex is True and transifexrc_name is set so that the transifex po files can be pulled to the correct directory
 - **use_transifex**: Use transifex to pull the latest po translation files to the django_locale_path directory (default: None) Note transifexrc_name and django_locale_path must be set if this argument is True
 - **transifexrc_name**: The name of the local transifexrc file that will be copied to the deployed server (default: None) Note this argument and django_locale_path must be set if use_transifex is True

### Useful DjangoStack Deployment Functions

```
add_pre_build_hook(func):
```

Calling this function on a DjangoStack instance with a function passed as the only argument, ensures that function is called before the instance executes any internal code.

```
add_post_build_hook(func):
```

Calling this function on a DjangoStack instance with a function passed as the only argument, ensures that function is called after the instance executes any internal code.

```
add_checkout(source_repository, destination, **kwargs):
```

Calling this function with source_repository and destination arguments will ensure that repository is cloned to the destination on the deployed server. This is done after the web server, database and Django are installed but before the web server is configured, database restored and configured and any Django operations are performed.
kwargs is an optional dictionary of keyword arguments that enables permissions, uid and gid to be set on repository directories and files. Expected format is:

```
**{
      'dir_attribs': [
          {
              'dir_path': '/var/django/', 'mode': None, 'owner': 'www-data', 'group': 'www-data',
              'recursive': True
          },
          {
              'dir_path': '/var/django/webfuels/', 'mode': None, 'owner': 'www-data',
              'group': 'www-data', 'recursive': True
          }
      ],
      'uids': [
          {
              'dir_path': '/var/django/webfuels/velocity/velocity/logs/', 'dirs': False,
              'files': True
          }
      ],
      'gids': [
          {'dir_path': '/var/django/webfuels/', 'dirs': True, 'files': True}
      ]
}
```


Please see https://github.com/hillman/djangostack/blob/master/docs/example_fabfile.py for an example fabfile.py

To deploy DjangoStack from this example fabfile run:

```
fab -H username@remote_server_ip:22 DeployFullStack
```

or from a vagrant machine:

```
fab -H vagrant@127.0.0.1:2222 DeployFullStack
```

Other options:
 - DeploySCM
 - DeployDatabase
 - DeployDjango
 - DeployWebServer

Note the end result is a call to setup_stack on the DjangoStack instance.

### SCM
**Important** If deploy_scm is True or repositories are added via the add_checkout function, a private and public bitbucket key must be provided that will enable DjangoStack to pull source code down to the deployment server. DjangoStack will look locally (i.e. in the same directory as the deployment fabfile) for 2 specific files which contain these keys: deploykey (private key) and deploykey.pub (public key).