#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" See COPYING for license information. """

__version__ = "1.8.0.0"
user_agent = "python-cloudfiles/%s" % __version__
# https and no port will support later
#chouti_authurl = 'https://auth.api.rackspacecloud.com/v1.0'
# for devauth
#chouti_authurl = 'http://chouti.roamin9.me:11000/v1.0'
# for swauth
chouti_authurl = 'http://chouti.roamin9.me:8080/auth/v1.0'
default_authurl = chouti_authurl

# swift object name, container name, meta name, meta value have some limits
meta_name_limit = 128
meta_value_limit = 256
object_name_limit = 1024
container_name_limit = 256

default_cdn_ttl = 5
