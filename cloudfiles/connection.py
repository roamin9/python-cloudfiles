#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
connection operations

Connection instances are used to communicate with the remote service at
the account level creating, listing and deleting Containers, and returning
Container instances.

See COPYING for license information.
"""

# 既然已经有了高级的httplib，为什么还要使用socket库呢？
import  socket
import  os
from    urllib    import quote
from    httplib   import HTTPSConnection, HTTPConnection, HTTPException
from    container import Container, ContainerResults
from    utils     import unicode_quote, parse_url, THTTPConnection, THTTPSConnection
from    errors    import ResponseError, NoSuchContainer, ContainerNotEmpty, \
                         InvalidContainerName
from    Queue     import Queue, Empty, Full
from    time      import time
import  consts
from    authentication import Authentication
from    fjson     import json_loads
from    sys       import version_info
# Because HTTPResponse objects *have* to have read() called on them
# before they can be used again ...
# pylint: disable-msg=W0612


class Connection(object):
    """
    Manages the connection to the storage system and serves as a factory
    for Container instances.

    create container ---> PUT
    delete container ---> DELETE
    rename container ---> POST  没实现
    set ACL          ---> POST  没实现
    get container    ---> GET
    get info         ---> HEAD
    list containers  ---> GET 解析json数据
    _authenticate ---> 认证
    http_connect  ---> 生成conn连接
    make_request  ---> 向服务端发送http请求
    """

    def __init__(self, username=None, api_key=None, timeout=5, **kwargs):
        """
        Accepts keyword arguments for chouti username and api key.
        Optionally, you can omit these keywords and supply an
        Authentication object using the auth keyword. 

        @type username: str
        @param username: a chouti username, pattern is account:admin
        @type api_key: str
        @param api_key: a chouti password
        container.
        """
        self.connection_args = None
        self.connection = None
        self.token = None
        self.debuglevel = int(kwargs.get('debuglevel', 0))
        self.servicenet = kwargs.get('servicenet', False)
        self.user_agent = kwargs.get('useragent', consts.user_agent)
        self.timeout = timeout

        self.auth = 'auth' in kwargs and kwargs['auth'] or None

        if not self.auth:
            authurl = kwargs.get('authurl', consts.chouti_authurl)
            if username and api_key and authurl:
                # 此处的auth为Authentication类的实例
                self.auth = Authentication(username, api_key, authurl=authurl,
                            useragent=self.user_agent)
            else:
                raise TypeError("Incorrect or invalid arguments supplied")

        self._authenticate()

    def _authenticate(self):
        """
        Authenticate and setup this instance with the values returned.
        私有方法，开始认证
        """
        (url, self.token) = self.auth.authenticate()
        self.connection_args = parse_url(url)

        if version_info[0] <= 2 and version_info[1] < 6:
            self.conn_class = self.connection_args[3] and THTTPSConnection or \
                                                              THTTPConnection
        else:
            self.conn_class = self.connection_args[3] and HTTPSConnection or \
                                                              HTTPConnection
        self.http_connect()

    def http_connect(self):
        """
        Setup the http connection instance.
        """
        (host, port, self.uri, is_ssl) = self.connection_args
        self.connection = self.conn_class(host, port=port, \
                                              timeout=self.timeout)
        self.connection.set_debuglevel(self.debuglevel)

    def make_request(self, method, path=[], data='', hdrs=None, parms=None):
        """
        Given a method (i.e. GET, PUT, POST, etc), a path, data, header and
        metadata dicts, and an optional dictionary of query parameters,
        performs an http request.
        
        @type method: str
        @param method: http method
        @type path: list
        @param path: the url's path, include [container_name], [obj_name]
        @type hdrs: dict
        @param hdrs: http headers
        @type parms: dict
        @param parms: query args
        """
        path = '/%s/%s' % \
                 (self.uri.rstrip('/'), '/'.join([unicode_quote(i) for i in path]))

        if isinstance(parms, dict) and parms:
                # 查询参数中的变量是固定的，为limits等字符，都为英文字符
                # 但查询参数中的值有可能是unicode值，
                # 因此，对于对于查询参数中的值需要进行unicode处理，使用unicode_quote()
                # 这应该算一个bug，可以提交给作者
            query_args = \
                ['%s=%s' % (unicode_quote(x),
                            unicode_quote(y)) for (x, y) in parms.items()]
            path = '%s?%s' % (path, '&'.join(query_args))

        headers = {
                   # 设置了Content-Length，这样上传或下载文件时需要优化一下
                   'Content-Length': str(len(data)),
                   'User-Agent': self.user_agent,
                   'X-Auth-Token': self.token
                   }
        isinstance(hdrs, dict) and headers.update(hdrs)

        def retry_request():
            '''Re-connect and re-try a failed request once'''
            self.http_connect()
            self.connection.request(method, path, data, headers)
            return self.connection.getresponse()

        try:
            self.connection.request(method, path, data, headers)
            response = self.connection.getresponse()
        except (socket.error, IOError, HTTPException):
            response = retry_request()
        if response.status == 401:
            self._authenticate()
            headers['X-Auth-Token'] = self.token
            response = retry_request()

        return response

    def get_info(self):
        """
        Return tuple for number of containers and total bytes in the account

        >>> connection.get_info()
        (5, 2309749)

        @rtype: tuple
        @return: a tuple containing the number of containers and total bytes
                 used by the account
        """
        response = self.make_request('HEAD')
        count = size = None
        for hdr in response.getheaders():
            if hdr[0].lower() == 'x-account-container-count':
                try:
                    count = int(hdr[1])
                except ValueError:
                    count = 0
            if hdr[0].lower() == 'x-account-bytes-used':
                try:
                    size = int(hdr[1])
                except ValueError:
                    size = 0
        buff = response.read()
        if (response.status < 200) or (response.status > 299):
            raise ResponseError(response.status, response.reason)
        return (count, size)

    def _check_container_name(self, container_name):
                # container名称中不能包含'/'
        if not container_name or \
                '/' in container_name or \
                len(container_name) > consts.container_name_limit:
            raise InvalidContainerName(container_name)

    def create_container(self, container_name):
        """
        Given a container name, returns a L{Container} item, creating a new
        Container if one does not already exist.

        >>> connection.create_container('new_container')
        <cloudfiles.container.Container object at 0xb77d628c>

        @param container_name: name of the container to create
        @type container_name: str
        @rtype: L{Container}
        @return: an object representing the newly created container
        """
        self._check_container_name(container_name)

        response = self.make_request('PUT', [container_name])
        buff = response.read()
        if (response.status < 200) or (response.status > 299):
            raise ResponseError(response.status, response.reason)
        return Container(self, container_name)

    def delete_container(self, container_name):
        """
        Given a container name, delete it.

        >>> connection.delete_container('old_container')

        @param container_name: name of the container to delete
        @type container_name: str
        """
        # Container类的实例
        if isinstance(container_name, Container):
            container_name = container_name.name
        self._check_container_name(container_name)

        response = self.make_request('DELETE', [container_name])

        if (response.status == 409):
            raise ContainerNotEmpty(container_name)
        elif (response.status == 404):
            raise NoSuchContainer
        elif (response.status < 200) or (response.status > 299):
            raise ResponseError(response.status, response.reason)

        # 一旦删除了一个container，需要标记CDN的状态为关闭
        #if self.cdn_enabled:
        #    response = self.cdn_request('POST', [container_name],
        #                        hdrs={'X-CDN-Enabled': 'False'})

    def get_all_containers(self, limit=None, marker=None, **parms):
        """
        Returns a Container item result set.

        >>> connection.get_all_containers()
        ContainerResults: 4 containers
        >>> print ', '.join([container.name for container in
                             connection.get_all_containers()])
        new_container, old_container, pictures, music

        @rtype: L{ContainerResults}
        @return: an iterable set of objects representing all containers on the
                 account
        @param limit: number of results to return, up to 10,000
        @type limit: int
        @param marker: return only results whose name is greater than "marker"
        @type marker: str
        """
        if limit:
            parms['limit'] = limit
        if marker:
            parms['marker'] = marker
        return ContainerResults(self, self.list_containers_info(**parms))

    def get_container(self, container_name):
        """
        Return a single Container item for the given Container.

        >>> connection.get_container('old_container')
        <cloudfiles.container.Container object at 0xb77d628c>
        >>> container = connection.get_container('old_container')
        >>> container.size_used
        23074

        @param container_name: name of the container to create
        @type container_name: str
        @rtype: L{Container}
        @return: an object representing the container
        """
        self._check_container_name(container_name)

        response = self.make_request('HEAD', [container_name])
        count = size = None
        for hdr in response.getheaders():
            if hdr[0].lower() == 'x-container-object-count':
                try:
                    count = int(hdr[1])
                except ValueError:
                    count = 0
            if hdr[0].lower() == 'x-container-bytes-used':
                try:
                    size = int(hdr[1])
                except ValueError:
                    size = 0
        buff = response.read()
        if response.status == 404:
            raise NoSuchContainer(container_name)
        if (response.status < 200) or (response.status > 299):
            raise ResponseError(response.status, response.reason)
        return Container(self, container_name, count, size)

    #def list_public_containers(self):
    #    """
    #    Returns a list of containers that have been published to the CDN.

    #    >>> connection.list_public_containers()
    #    ['container1', 'container2', 'container3']

    #    @rtype: list(str)
    #    @return: a list of all CDN-enabled container names as strings
    #    """
    #    response = self.cdn_request('GET', [''])
    #    if (response.status < 200) or (response.status > 299):
    #        buff = response.read()
    #        raise ResponseError(response.status, response.reason)
    #    return response.read().splitlines()

    def list_containers_info(self, limit=None, marker=None, **parms):
        """
        Returns a list of Containers, including object count and size.

        >>> connection.list_containers_info()
        [{u'count': 510, u'bytes': 2081717, u'name': u'new_container'},
         {u'count': 12, u'bytes': 23074, u'name': u'old_container'},
         {u'count': 0, u'bytes': 0, u'name': u'container1'},
         {u'count': 0, u'bytes': 0, u'name': u'container2'},
         {u'count': 0, u'bytes': 0, u'name': u'container3'},
         {u'count': 3, u'bytes': 2306, u'name': u'test'}]

        @rtype: list({"name":"...", "count":..., "bytes":...})
        @return: a list of all container info as dictionaries with the
                 keys "name", "count", and "bytes"
        @param limit: number of results to return, up to 10,000
        @type limit: int
        @param marker: return only results whose name is greater than "marker"
        @type marker: str
        """
        if limit:
            parms['limit'] = limit
        if marker:
            parms['marker'] = marker
        parms['format'] = 'json'
        response = self.make_request('GET', [''], parms=parms)
        if (response.status < 200) or (response.status > 299):
            buff = response.read()
            raise ResponseError(response.status, response.reason)
        return json_loads(response.read())

    def list_containers(self, limit=None, marker=None, **parms):
        """
        Returns a list of Containers.

        >>> connection.list_containers()
        ['new_container',
         'old_container',
         'container1',
         'container2',
         'container3',
         'test']

        @rtype: list(str)
        @return: a list of all containers names as strings
        @param limit: number of results to return, up to 10,000
        @type limit: int
        @param marker: return only results whose name is greater than "marker"
        @type marker: str
        """
        if limit:
            parms['limit'] = limit
        if marker:
            parms['marker'] = marker
        response = self.make_request('GET', [''], parms=parms)
        if (response.status < 200) or (response.status > 299):
            buff = response.read()
            raise ResponseError(response.status, response.reason)
        return response.read().splitlines()

    def __getitem__(self, key):
        """
        Container objects can be grabbed from a connection using index
        syntax.

        >>> container = conn['old_container']
        >>> container.size_used
        23074

        @rtype: L{Container}
        @return: an object representing the container
        """
        return self.get_container(key)


class ConnectionPool(Queue):
    """
    A thread-safe connection pool object.

    This component isn't required when using the cloudfiles library, but it may
    be useful when building threaded applications.
    """

    def __init__(self, username=None, api_key=None, **kwargs):
        auth = kwargs.get('auth', None)
        self.timeout = kwargs.get('timeout', 5)
        self.connargs = {'username': username, 'api_key': api_key}
        poolsize = kwargs.get('poolsize', 10)
        Queue.__init__(self, poolsize)

    def get(self):
        """
        Return a cloudfiles connection object.

        @rtype: L{Connection}
        @return: a cloudfiles connection object
        """
        try:
            (create, connobj) = Queue.get(self, block=0)
        except Empty:
            # 此处生成连接池时，传递的参数有误，应该为bug，可以报告给作者
            #connobj = Connection(**self.connargs)
            connobj = Connection(username=self.connargs.get('username'), 
                    api_key=self.connargs.get('api_key'))
        return connobj

    def put(self, connobj):
        """
        Place a cloudfiles connection object back into the pool.

        @param connobj: a cloudfiles connection object
        @type connobj: L{Connection}
        """
        try:
            Queue.put(self, (time(), connobj), block=0)
        except Full:
            del connobj
# vim:set ai sw=4 ts=4 tw=0 expandtab:
