#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
container operations

Containers are storage compartments where you put your data (objects).
A container is similar to a directory or folder on a conventional filesystem
with the exception that they exist in a flat namespace, you can not create
containers inside of containers.

See COPYING for license information.
"""

from storage_object import Object, ObjectResults
from errors import ResponseError, InvalidContainerName, InvalidObjectName
from utils  import requires_name
import consts
from fjson  import json_loads

# Because HTTPResponse objects *have* to have read() called on them
# before they can be used again ...
# pylint: disable-msg=W0612


class Container(object):
    """
    Container object and Object instance factory.

    @ivar name: the container's name (generally treated as read-only)
    @type name: str
    @ivar object_count: the number of objects in this container (cached)
                        object数量是缓存的，所以导致不能及时更新？
    @type object_count: number
    @ivar size_used: the sum of the sizes of all objects in this container
            (cached)
    @type size_used: number

    _list_objects_raw ---> 发送http请求
    """
    def __set_name(self, name):
        # 检查名称的合法性
        # slashes make for invalid names
        # 此处的container名称既可以是str，也可以是unicode，可能会引起一些误会
        # 不如统一起来
        if isinstance(name, (str, unicode)) and \
                ('/' in name or len(name) > consts.container_name_limit):
            raise InvalidContainerName(name)
        self._name = name

    name = property(fget=lambda self: self._name, fset=__set_name,
        doc="the name of the container (read-only)")

    def __init__(self, connection=None, name=None, count=None, size=None):
        """
        Containers will rarely if ever need to be instantiated directly by the
        user.

        Instead, use the L{create_container<Connection.create_container>},
        L{get_container<Connection.get_container>},
        L{list_containers<Connection.list_containers>} and
        other methods on a valid Connection object.
        """
        self._name = None
        self.name = name
        self.conn = connection
        self.object_count = count
        self.size_used = size

    @requires_name(InvalidContainerName)
    def create_object(self, object_name):
        """
        Return an L{Object} instance, creating it if necessary.

        When passed the name of an existing object, this method will
        return an instance of that object, otherwise it will create a
        new one.

        >>> container.create_object('new_object')
        <cloudfiles.storage_object.Object object at 0xb778366c>
        >>> obj = container.create_object('new_object')
        >>> obj.name
        'new_object'

        @type object_name: str
        @param object_name: the name of the object to create
        @rtype: L{Object}
        @return: an object representing the newly created storage object
        """
        return Object(self, object_name)

    @requires_name(InvalidContainerName)
    def get_objects(self, prefix=None, limit=None, marker=None,
                    path=None, delimiter=None, **parms):
        """
        Return a result set of all Objects in the Container.

        Keyword arguments are treated as HTTP query parameters and can
        be used to limit the result set (see the API documentation).

        >>> container.get_objects(limit=2)
        ObjectResults: 2 objects
        >>> for obj in container.get_objects():
        ...     print obj.name
        new_object
        old_object

        @param prefix: filter the results using this prefix
        @type prefix: str
        @param limit: return the first "limit" objects found
        @type limit: int
        @param marker: return objects whose names are greater than "marker"
        @type marker: str
        @param path: return all objects in "path"
        @type path: str
        @param delimiter: use this character as a delimiter for subdirectories
        @type delimiter: char

        @rtype: L{ObjectResults}
        @return: an iterable collection of all storage objects in the container
        """
        return ObjectResults(self, self.list_objects_info(
                prefix, limit, marker, path, delimiter, **parms))

    @requires_name(InvalidContainerName)
    def get_object(self, object_name):
        """
        Return an L{Object} instance for an existing storage object.

        If an object with a name matching object_name does not exist
        then a L{NoSuchObject} exception is raised.

        >>> obj = container.get_object('old_object')
        >>> obj.name
        'old_object'

        @param object_name: the name of the object to retrieve
        @type object_name: str
        @rtype: L{Object}
        @return: an Object representing the storage object requested
        """
        return Object(self, object_name, force_exists=True)

    @requires_name(InvalidContainerName)
    def list_objects_info(self, prefix=None, limit=None, marker=None,
                          path=None, delimiter=None, **parms):
        """
        Return information about all objects in the Container.

        Keyword arguments are treated as HTTP query parameters and can
        be used limit the result set (see the API documentation).

        >>> conn['container1'].list_objects_info(limit=2)
        [{u'bytes': 4820,
          u'content_type': u'application/octet-stream',
          u'hash': u'db8b55400b91ce34d800e126e37886f8',
          u'last_modified': u'2008-11-05T00:56:00.406565',
          u'name': u'new_object'},
         {u'bytes': 1896,
          u'content_type': u'application/octet-stream',
          u'hash': u'1b49df63db7bc97cd2a10e391e102d4b',
          u'last_modified': u'2008-11-05T00:56:27.508729',
          u'name': u'old_object'}]

        @param prefix: filter the results using this prefix
        @type prefix: str
        @param limit: return the first "limit" objects found
        @type limit: int
        @param marker: return objects with names greater than "marker"
        @type marker: str
        @param path: return all objects in "path"
        @type path: str
        @param delimiter: use this character as a delimiter for subdirectories
        @type delimiter: char

        @rtype: list({"name":"...", "hash":..., "size":..., "type":...})
        @return: a list of all container info as dictionaries with the
                 keys "name", "hash", "size", and "type"
        """
        parms['format'] = 'json'
        resp = self._list_objects_raw(
            prefix, limit, marker, path, delimiter, **parms)
        return json_loads(resp)

    @requires_name(InvalidContainerName)
    def list_objects(self, prefix=None, limit=None, marker=None,
                     path=None, delimiter=None, **parms):
        """
        Return names of all L{Object}s in the L{Container}.

        Keyword arguments are treated as HTTP query parameters and can
        be used to limit the result set (see the API documentation).

        >>> container.list_objects()
        ['new_object', 'old_object']

        @param prefix: filter the results using this prefix
        @type prefix: str
        @param limit: return the first "limit" objects found
        @type limit: int
        @param marker: return objects with names greater than "marker"
        @type marker: str
        @param path: return all objects in "path"
        @type path: str
        @param delimiter: use this character as a delimiter for subdirectories
        @type delimiter: char

        @rtype: list(str)
        @return: a list of all container names
        """
        resp = self._list_objects_raw(prefix=prefix, limit=limit,
                                      marker=marker, path=path,
                                      delimiter=delimiter, **parms)
        return resp.splitlines()

    @requires_name(InvalidContainerName)
    def _list_objects_raw(self, prefix=None, limit=None, marker=None,
                          path=None, delimiter=None, **parms):
        """
        Returns a chunk list of storage object info.
        """
        if prefix:
            parms['prefix'] = prefix
        if limit:
            parms['limit'] = limit
        if marker:
            parms['marker'] = marker
        if delimiter:
            parms['delimiter'] = delimiter
        if not path is None:
            parms['path'] = path  # empty strings are valid
        response = self.conn.make_request('GET', [self.name], parms=parms)
        if (response.status < 200) or (response.status > 299):
            response.read()
            raise ResponseError(response.status, response.reason)
        return response.read()

    def __getitem__(self, key):
        return self.get_object(key)

    def __str__(self):
        return self.name

    @requires_name(InvalidContainerName)
    def delete_object(self, object_name):
        """
        Permanently remove a storage object.

        >>> container.list_objects()
        ['new_object', 'old_object']
        >>> container.delete_object('old_object')
        >>> container.list_objects()
        ['new_object']

        @param object_name: the name of the object to retrieve
        @type object_name: str
        """
        if isinstance(object_name, Object):
            object_name = object_name.name
        if not object_name:
            raise InvalidObjectName(object_name)
        response = self.conn.make_request('DELETE', [self.name, object_name])
        if (response.status < 200) or (response.status > 299):
            response.read()
            raise ResponseError(response.status, response.reason)
        response.read()


class ContainerResults(object):
    """
    An iterable results set object for Containers.

    This class implements dictionary- and list-like interfaces.
    """
    def __init__(self, conn, containers=list()):
        self._containers = containers
        self._names = [k['name'] for k in containers]
        self.conn = conn

    def __getitem__(self, key):
        return Container(self.conn,
                         self._containers[key]['name'],
                         self._containers[key]['count'],
                         self._containers[key]['bytes'])

    def __getslice__(self, i, j):
        return [Container(self.conn, k['name'], k['count'], \
                              k['size']) for k in self._containers[i:j]]

    def __contains__(self, item):
        return item in self._names

    def __repr__(self):
        return 'ContainerResults: %s containers' % len(self._containers)
    __str__ = __repr__

    def __len__(self):
        return len(self._containers)

    def index(self, value, *args):
        """
        returns an integer for the first index of value
        """
        return self._names.index(value, *args)

    def count(self, value):
        """
        returns the number of occurrences of value
        """
        return self._names.count(value)

# vim:set ai sw=4 ts=4 tw=0 expandtab:
