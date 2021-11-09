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

from nti.app.contenttypes.completion import PROGRESS_PATH_NAME
from nti.app.contenttypes.completion import COMPLETION_PATH_NAME
from nti.app.contenttypes.completion import BUILD_COMPLETION_VIEW
from nti.app.contenttypes.completion import RESET_COMPLETION_VIEW
from nti.app.contenttypes.completion import COMPLETED_ITEMS_PATH_NAME
from nti.app.contenttypes.completion import USER_DATA_COMPLETION_VIEW
from nti.app.contenttypes.completion import COMPLETABLE_ITEMS_PATH_NAME
from nti.app.contenttypes.completion import COMPLETION_POLICY_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETION_DEFAULT_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETION_REQUIRED_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETION_NOT_REQUIRED_VIEW_NAME
from nti.app.contenttypes.completion import DEFAULT_REQUIRED_POLICY_PATH_NAME
from nti.app.contenttypes.completion import AWARDED_COMPLETED_ITEMS_PATH_NAME
from nti.app.contenttypes.completion import DELETE_AWARDED_COMPLETED_ITEM_VIEW

from nti.app.contenttypes.completion.interfaces import ICompletedItemsContext
from nti.app.contenttypes.completion.interfaces import IAwardedCompletedItemsContext
from nti.app.contenttypes.completion.interfaces import ICompletionContextACLProvider
from nti.app.contenttypes.completion.interfaces import ICompletionContextUserProgress

from nti.app.externalization.error import raise_json_error

from nti.contenttypes.completion.interfaces import ICompletionContext
from nti.contenttypes.completion.interfaces import ICompletionContextProgress

from nti.dataserver.authorization import ROLE_ADMIN

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import ace_denying_all

from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.dataserver.interfaces import IUser

from nti.dataserver.users import User

from nti.links.links import Link

from nti.traversal.traversal import find_interface


def raise_error(data, tb=None,
                factory=hexc.HTTPUnprocessableEntity,
                request=None):
    request = request or get_current_request()
    raise_json_error(request, factory, data, tb)


class CompletionContextMixin(object):

    @property
    def completion_context(self):
        return find_interface(self, ICompletionContext, strict=False)

    @Lazy
    def __acl__(self):
        provider = component.queryMultiAdapter((self.completion_context, self),
                                               ICompletionContextACLProvider)
        if provider is None:
            # For tests
            aces = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)),
                    ace_denying_all()]
            result = acl_from_aces(aces)
        else:
            result = provider.__acl__
        return result


_USERS_SUBPATH = u'users'

class UserTraversableMixin(object):

    CONSUME_SUBPATH = True

    def traverse(self, subpath, remaining):
        if self.user is not None:
            raise LocationError(subpath)

        username = subpath
        if self.CONSUME_SUBPATH:
            if not remaining or subpath != _USERS_SUBPATH:
                raise LocationError(subpath)
            username = remaining.pop(0)

        user = User.get_user(username)
        if user is None:
            raise LocationError(username)
        self.user = user
        return self

    def __conform__(self, iface):
        if IUser.isOrExtends(iface):
            return self.user
        return None


@interface.implementer(IPathAdapter)
class CompletionPathAdapter(Contained):

    __name__ = COMPLETION_PATH_NAME

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.__parent__ = context


@interface.implementer(IPathAdapter)
@interface.implementer(ITraversable)
class CompletableItemsPathAdapter(Contained, CompletionContextMixin, UserTraversableMixin):

    __name__ = COMPLETABLE_ITEMS_PATH_NAME

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.__parent__ = context
        self.user = None


def completed_items_link(completion_context, user):
    return Link(completion_context,
                rel='CompletedItems',
                elements=('Completion', 'CompletedItems', 'users', user.username))


@interface.implementer(IPathAdapter)
@interface.implementer(ICompletedItemsContext)
@interface.implementer(ITraversable)
class CompletedItemsPathAdapter(Contained, CompletionContextMixin, UserTraversableMixin):

    __name__ = COMPLETED_ITEMS_PATH_NAME

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.__parent__ = context
        self.user = None


def progress_link(completion_context, user=None, rel=None, view_name=None):
    elements = ['Completion', 'Progress']
    if user:
        elements.extend(['users', user.username])
    if view_name:
        elements.append('@@'+view_name)
    return Link(completion_context,
                rel=rel,
                elements=elements)


@interface.implementer(IPathAdapter)
@interface.implementer(ICompletionContextProgress)
class ProgressPathAdapter(Contained, CompletionContextMixin):

    __name__ = PROGRESS_PATH_NAME

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.__parent__ = context

@interface.implementer(IPathAdapter)
@interface.implementer(ICompletionContextUserProgress)
@interface.implementer(ITraversable)
class UsersProgressPathAdapter(Contained, CompletionContextMixin, UserTraversableMixin):

    CONSUME_SUBPATH = False

    __name__ = _USERS_SUBPATH

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.__parent__ = context
        self.user = None

def awarded_completed_items_link(completion_context, user):
    return Link(completion_context,
                rel=AWARDED_COMPLETED_ITEMS_PATH_NAME,
                elements=('Completion', AWARDED_COMPLETED_ITEMS_PATH_NAME, 'users', user.username))

@interface.implementer(IPathAdapter)
@interface.implementer(IAwardedCompletedItemsContext)
@interface.implementer(ITraversable)
class AwardedCompletedItemsPathAdapter(Contained, CompletionContextMixin, UserTraversableMixin):
    
    __name__ = AWARDED_COMPLETED_ITEMS_PATH_NAME
    
    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.__parent__ = context
        self.user = None
        
