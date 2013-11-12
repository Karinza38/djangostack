from taskset import TaskSet, task_method
from fabric.api import *
from fabric.contrib.files import exists
from cuisine import *
from cuisine_postgresql import postgresql_role_ensure, postgresql_database_ensure
import time

class DjangoStack(TaskSet):

    DEFAULT_PYTHON_DEPENDENCIES=['psycopg2','django','south']
    DEFAULT_ADDITIONAL_PACKAGES=['vim',]
    DEFAULT_DJANGO_ADMIN_USER='admin'
    DEFAULT_DJANGO_ADMIN_PASSWORD='notagoodpassword'
    DEFAULT_DJANGO_ADMIN_EMAIL='admin@example.com'

    def __init__(self,projectName,apacheConfigName='apache_site',scmType='mercurial',databaseName=None,databaseUser=None,databasePassword=None,djangoProjectPath=None,
                    djangoAdminUser=DEFAULT_DJANGO_ADMIN_USER, djangoAdminEmail=DEFAULT_DJANGO_ADMIN_EMAIL,
                    djangoAdminPassword=DEFAULT_DJANGO_ADMIN_PASSWORD,databaseDumpType='SQL'):
        self.PROJECT_NAME=projectName
        self.PYTHON_DEPENDENCIES=self.DEFAULT_PYTHON_DEPENDENCIES
        self.SCM_TYPE=scmType
        self.DATABASE_NAME=databaseName
        self.DATABASE_USER=databaseUser
        self.DATABASE_PASSWORD=databasePassword
        self.DJANGO_PROJECT_PATH=djangoProjectPath
        self.DJANGO_ADMIN_USER=djangoAdminUser
        self.DJANGO_ADMIN_PASSWORD=djangoAdminPassword
        self.DJANGO_ADMIN_EMAIL=djangoAdminEmail
        self.APACHE_CONFIG_NAME=apacheConfigName
        self.DATABASE_DUMP_TYPE=databaseDumpType
        self.repositories=[]
        self.packages=[]
        self.packages.extend(self.DEFAULT_ADDITIONAL_PACKAGES)

        self.postBuildHooks=[]

        # check for deploy key file

        # check for apache config file


    def addAdditionalPythonDep(self,dependency):
        self.PYTHON_DEPENDENCIES.append(dependency)

    def addAdditionalPackage(self,packageName):
        self.packages.append(packageName)

    def addCheckout(self,sourceRepository,destination):
        self.repositories.append([sourceRepository,destination])

    def addPostBuildHook(self,func):
        self.postBuildHooks.append(func)

    @task_method
    def runPostBuildHooks(self):
        for hook in self.postBuildHooks:
            hook()

    @task_method(default=True)
    def setupStack(self):
        package_update()
        self.setupScm()
        self.setupApache()
        self.setupPostgres()
        self.setupAdditionalPackages()
        self.setupPython()

        self.createDatabaseUser()
        self.createDatabase()
        self.createApacheSite()
        
        self.setupBitbucketKey()
        self.checkoutCode()

        self.restoreDatabaseDump()

        self.runPostBuildHooks()

        self.restartServices()

    @task_method
    def setupAdditionalPackages(self):
        for packageName in self.packages:
            package_ensure(packageName)

    @task_method
    def checkoutCode(self):
        if self.SCM_TYPE.lower()=='mercurial':
            scm_command="hg clone"
        elif self.SCM_TYPE.lower()=='git':
            scm_command="git clone"
        for sourceRepository, destination in self.repositories:
            with mode_sudo():
                run("%s %s %s"%(scm_command,sourceRepository,destination))

    @task_method
    def setupPython(self):
        package_ensure("build-essential")
        package_ensure("python")
        package_ensure("python-dev")
        package_ensure("python-pip")

        with mode_sudo():
            for dependency in self.PYTHON_DEPENDENCIES:
                run("pip install %s"%dependency)

    @task_method
    def setupApache(self):
        hadApache=package_ensure("apache2")

        package_ensure("libapache2-mod-wsgi")
        with mode_sudo():
            run("a2enmod rewrite")

        if not hadApache and hasattr(env,"vagrantMode"):
            local("vagrant reload")
            time.sleep(15)
    

    @task_method
    def useVagrant(self):
        env.user = 'vagrant'
        env.hosts = ['127.0.0.1:2222']
        env.vagrantMode=True
  
        # retrieve the IdentityFile:
        result = local('vagrant ssh-config | grep IdentityFile', capture=True)
        env.key_filename = result.split()[1][1:-1] # parse IdentityFile


    @task_method
    def setupPostgres(self):
        package_ensure("postgresql")
        package_ensure("postgresql-client")
        package_ensure("libpq-dev")
        

    @task_method
    def setupScm(self):
        if self.SCM_TYPE=='mercurial':
            package_ensure("mercurial")
        elif self.SCM_TYPE.lower()=='git':
            package_ensure("git")
        

    @task_method
    def createDatabaseUser(self):
        postgresql_role_ensure(self.DATABASE_USER,self.DATABASE_PASSWORD,createdb=True)

    @task_method
    def createDatabase(self):
        postgresql_database_ensure(self.DATABASE_NAME,owner=self.DATABASE_USER,encoding='utf8',template='template0',locale='en_US.UTF-8')

    @task_method
    def createApacheSite(self):
        put("%s"%self.APACHE_CONFIG_NAME,"/etc/apache2/sites-enabled/%s"%self.PROJECT_NAME,use_sudo=True)

        if exists("/etc/apache2/sites-enabled/000-default"):
            sudo("rm /etc/apache2/sites-enabled/000-default")

    @task_method
    def setupBitbucketKey(self):
        with mode_sudo():
            dir_ensure("/root/.ssh/")
        put("deploykey","~/id_rsa")
        put("deploykey.pub","~/id_rsa.pub")
        sudo("mv ~/id_rsa /root/.ssh/")
        sudo("mv ~/id_rsa.pub /root/.ssh/")
        bitbuckethost="bitbucket.org ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAubiN81eDcafrgMeLzaFPsw2kNvEcqTKl/VqLat/MaB33pZy0y3rJZtnqwR2qOOvbwKZYKiEO1O6VqNEBxKvJJelCq0dTXWT5pbO2gDXC6h6QDXCaHo6pOHGPUy+YBaGQRGuSusMEASYiWunYN0vCAI8QaXnWMXNMdFP3jHAJH0eDsoiGnLPBlBp4TNm6rYI74nMzgz3B9IikW4WVK+dc8KZJZWYjAuORU3jc1c/NPskD2ASinf8v3xnfXeukU0sJ5N6m5E8VLjObPEO+mN2t/FZTMZLiFqPWc/ALSqnMnnhwrNi2rbfg/rd/IpL8Le3pSBne8+seeFVBoGqzHM9yXw=="
        sudo("echo '%s' >> /root/.ssh/known_hosts"%bitbuckethost)

    @task_method
    def restoreDatabaseDump(self):
        if not exists("/var/lib/postgresql/dbdump.txt"):
            put("dbdump.txt","/var/lib/postgresql/",use_sudo=True)
        sudo("chown postgres /var/lib/postgresql/dbdump.txt")

        if self.DATABASE_DUMP_TYPE=="SQL":
            sudo("cd /var/lib/postgresql; psql %s < dbdump.txt"%self.DATABASE_NAME,user="postgres")
        else:
            sudo("cd /var/lib/postgresql; pg_restore -d %s dbdump.txt"%self.DATABASE_NAME,user="postgres")

    @task_method
    def syncDb(self):
        with mode_sudo():
            run("cd %s;python manage.py syncdb --noinput; python manage.py migrate --noinput;"%(self.DJANGO_PROJECT_PATH))

    @task_method
    def restartServices(self):
        sudo("service apache2 restart")
        sudo("service postgresql restart")

    @task_method
    def createDjangoAdminUser(self):
        # TODO: make this idempotent:
        sudo("cd %s;echo \"from django.contrib.auth.models import User; User.objects.create_superuser('%s', '%s', '%s')\" | ./manage.py shell"%(self.DJANGO_PROJECT_PATH,self.DJANGO_ADMIN_USER,self.DJANGO_ADMIN_EMAIL,self.DJANGO_ADMIN_PASSWORD))


