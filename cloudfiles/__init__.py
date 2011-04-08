#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
chouti python client API.

Working with result sets:

    >>> import cloudfiles
    >>> # conn = cloudfiles.get_connection(username='account:user', \
                 api_key='pwd', authurl= cloudfiles.chouti_authurl)
    >>> containers = conn.get_all_containers()
    >>> type(containers)
    <class 'cloudfiles.container.ContainerResults'>
    >>> len(containers)
    2
    >>> for container in containers:
    >>>     print container.name
    fruit
    vegitables
    >>> print containers[0].name
    fruit
    >>> fruit_container = containers[0]
    >>> objects = fruit_container.get_objects()
    >>> for storage_object in objects:
    >>>     print storage_object.name
    apple
    orange
    bannana
    >>>

Creating Containers and adding Objects to them:

    >>> pic_container = conn.create_container('pictures')
    >>> my_dog = pic_container.create_object('fido.jpg')
    >>> my_dog.load_from_filename('images/IMG-0234.jpg')
    >>> text_obj = pic_container.create_object('sample.txt')
    >>> text_obj.write('This is not the object you are looking for.\\n')
    >>> text_obj.read()
    'This is not the object you are looking for.'

Object instances support streaming through the use of a generator:

    >>> deb_iso = pic_container.get_object('debian-40r3-i386-netinst.iso')
    >>> f = open('/tmp/debian.iso', 'w')
    >>> for chunk in deb_iso.stream():
    ..     f.write(chunk)
    >>> f.close()

See COPYING for license information.
"""

from cloudfiles.connection     import Connection, ConnectionPool
from cloudfiles.container      import Container
from cloudfiles.storage_object import Object
from cloudfiles.consts         import __version__, \
chouti_authurl


def get_connection(*args, **kwargs):
    """
    Helper function for creating connection instances.

    @type username: string
    @param username: account:user
    @type api_key: string
    @param api_key: pwd
    @rtype: L{Connection}
    @returns: a connection object
    """
    return Connection(*args, **kwargs)
