from distutils.core import setup

setup(
    name='DjangoStack',
    version='0.2.0',
    author='Jamie Hillman',
    author_email='mail@jamiehillman.co.uk',
    packages=['djangostack'],
    description='fabric/cuisine-based script for configuring django-based servers',
    install_requires=[
        'fabric',
        'cuisine',
        'cuisine_postgresql',
        'fabric-taskset'
    ]
)
