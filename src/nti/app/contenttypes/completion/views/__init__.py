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

from zope.cachedescriptors.property import Lazy

from zope.container.contained import Contained

from zope.location.interfaces import LocationError

from zope.traversing.interfaces import IPathAdapter
from zope.traversing.interfaces import ITraversable

from nti.app.contenttypes.completion import MessageFactory

from nti.app.contenttypes.completion import COMPLETED_ITEMS_PATH_NAME
from nti.app.contenttypes.completion import COMPLETION_PATH_NAME
from nti.app.contenttypes.completion import COMPLETABLE_ITEMS_PATH_NAME
from nti.app.contenttypes.completion import COMPLETION_POLICY_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETION_DEFAULT_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETION_REQUIRED_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETION_NOT_REQUIRED_VIEW_NAME
from nti.app.contenttypes.completion import DEFAULT_REQUIRED_POLICY_PATH_NAME

from nti.app.contenttypes.completion.interfaces import ICompletedItemsContext
from nti.app.contenttypes.completion.interfaces import ICompletionContextACLProvider

from nti.app.externalization.error import raise_json_error

from nti.contenttypes.completion.interfaces import ICompletionContext

from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import ace_denying_all

from nti.dataserver.users import User

from nti.traversal.traversal import find_interface

def raise_error(data, tb=None,
                factory=hexc.HTTPUnprocessableEntity,
                request=None):
    request = request or get_current_request()
    raise_json_error(request, factory, data, tb)


@interface.implementer(IPathAdapter)
class CompletionPathAdapter(Contained):

    __name__ = COMPLETION_PATH_NAME

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.__parent__ = context


@interface.implementer(IPathAdapter)
class CompletableItemsPathAdapter(Contained):

    __name__ = COMPLETABLE_ITEMS_PATH_NAME

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.__parent__ = context


_USERS_SUBPATH = u'users'


@interface.implementer(IPathAdapter)
@interface.implementer(ICompletedItemsContext)
@interface.implementer(ITraversable)
class CompletedItemsPathAdapter(Contained):

    __name__ = COMPLETED_ITEMS_PATH_NAME

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.__parent__ = context
        self.user = None

    @property
    def completion_context(self):
        return find_interface(self, ICompletionContext, strict=False)

    def traverse(self, subpath, remaining):
        if self.user is not None or subpath != _USERS_SUBPATH:
            raise LocationError(subpath)

        if remaining:
            username = remaining.pop(0)
            user = User.get_user(username)
            if user is None:
                raise LocationError(username)
            self.user = user

        return self

    @Lazy
    def __acl__(self):
        provider = component.queryMultiAdapter((self.completion_context, self), ICompletionContextACLProvider)
        return provider.__acl__ if provider is not None else acl_from_aces(ace_denying_all())
