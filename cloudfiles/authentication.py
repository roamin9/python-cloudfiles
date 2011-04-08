#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
authentication operations

Authentication instances are used to interact with the remote
authentication service, retreiving storage system routing information
and session tokens.

See COPYING for license information.
"""

from httplib  import HTTPSConnection, HTTPConnection
# will try use httplib2 as http client
#import httplib2
from utils    import parse_url, THTTPConnection, THTTPSConnection
from errors   import ResponseError, AuthenticationError, AuthenticationFailed
from consts   import user_agent, chouti_authurl
from sys      import version_info


class BaseAuthentication(object):
    """
    The base authentication class from which all others inherit.
    """
    def __init__(self, username, api_key, authurl=chouti_authurl, timeout=5,
                 useragent=user_agent):
        self.authurl = authurl
        self.headers = dict()
        self.headers['x-auth-user'] = username
        self.headers['x-auth-key'] = api_key
        self.headers['User-Agent'] = useragent
        self.timeout = timeout
        (self.host, self.port, self.uri, self.is_ssl) = parse_url(self.authurl)
        if version_info[0] <= 2 and version_info[1] < 6:
            # 兼容python 2.6以下的版本
            # 注意下面 and 和 or 的用法
            self.conn_class = self.is_ssl and THTTPSConnection or \
                THTTPConnection
        else:
            # 生成了http client的连接类
            self.conn_class = self.is_ssl and HTTPSConnection or HTTPConnection

    def authenticate(self):
        """
        Initiates authentication with the remote service and returns a
        two-tuple containing the storage system URL and session token.

        Note: This is a dummy method from the base class. It must be
        overridden by sub-classes.
        """
        # 返回的应该为2元组，此处的3元组包含了cdn_url
        # 包括：(storage_url, cdn_url, token)
        return (None, None, None)


#class MockAuthentication(BaseAuthentication):
#    """
#    Mock authentication class for testing
#    """
#    def authenticate(self):
#        return ('http://localhost/v1/account', None, 'xxxxxxxxx')


class Authentication(BaseAuthentication):
    """
    Authentication, routing, and session token management.
    The default timeout is 5 seconds.
    """
    def authenticate(self):
        """
        Initiates authentication with the remote service and returns a
        two-tuple containing the storage system URL and session token.
        """
        # 产生连接的实例
        # 传递的三个参数，是httplib.HTTPConnection需要的
        conn = self.conn_class(self.host, self.port, timeout=self.timeout)
        conn.request('GET', '/' + self.uri, headers=self.headers)
        # 获得服务器端的响应
        response = conn.getresponse()
        response.read()

        # A status code of 401 indicates that the supplied credentials
        # were not accepted by the authentication service.
        if response.status == 401:
            raise AuthenticationFailed()

        # Raise an error for any response that is not 2XX
        # 为什么使用 // ？
        #if response.status // 100 != 2:
        if response.status / 100 != 2:
            raise ResponseError(response.status, response.reason)

        storage_url = auth_token = None

        # 解析http headers
        for hdr in response.getheaders():
            if hdr[0].lower() == "x-storage-url":
                storage_url = hdr[1]
            # swift 不支持CDN，我们把它搞去
            # 保留此处是为了记住包含CDN信息的HTTP头的处理方法
            #if hdr[0].lower() == "x-cdn-management-url":
            #    cdn_url = hdr[1]
            if hdr[0].lower() == "x-storage-token":
                auth_token = hdr[1]
            if hdr[0].lower() == "x-auth-token":
                auth_token = hdr[1]

        # 连接关闭
        conn.close()

        if not (auth_token and storage_url):
            raise AuthenticationError("Invalid response from the " \
                    "authentication service.")

        return (storage_url, auth_token)

# vim:set ai ts=4 sw=4 tw=0 expandtab:
