from djangostack import *

def sampleSitePostBuild():
	print "postbuild"

cpsite = DjangoStack('samplesite',apacheConfigName='apache_site',scmType="hg",databaseName='sampledb',
	databaseUser='dbuser',databasePassword='dbpassword',
	)

cpsite.addCheckout("ssh://hg@bitbucket.org/username/project","/var/www/projectroot/")



cpsite.addAdditionalPythonDep("python-memcached")

cpsite.addPostBuildHook(cpsitePostBuild)

cpsite.expose_to_current_module()