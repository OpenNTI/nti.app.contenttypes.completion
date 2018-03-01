#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid import httpexceptions as hexc

from pyramid.threadlocal import get_current_request

from zope import component
from zope import interface

from zope.container.contained import Contained

from zope.traversing.interfaces import IPathAdapter

from nti.app.contenttypes.completion import MessageFactory

from nti.app.contenttypes.completion import COMPLETION_POLICY_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETION_REQUIRED_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETION_NOT_REQUIRED_VIEW_NAME

from nti.app.externalization.error import raise_json_error


def raise_error(data, tb=None,
                factory=hexc.HTTPUnprocessableEntity,
                request=None):
    request = request or get_current_request()
    raise_json_error(request, factory, data, tb)
