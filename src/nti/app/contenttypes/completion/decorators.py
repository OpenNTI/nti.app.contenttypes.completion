#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: decorators.py 113814 2017-05-31 02:18:58Z josh.zuech $
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.location.interfaces import ILocation

from nti.app.contenttypes.completion import COMPLETION_POLICY_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETION_REQUIRED_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETION_NOT_REQUIRED_VIEW_NAME
from nti.app.contenttypes.completion import DEFAULT_REQUIRED_POLICY_PATH_NAME

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.completion.interfaces import ICompletableItem
from nti.contenttypes.completion.interfaces import ICompletionContext
from nti.contenttypes.completion.interfaces import ICompletableItemContainer
from nti.contenttypes.completion.interfaces import ICompletableItemDefaultRequiredPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicyContainer

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.authorization import is_admin_or_content_admin_or_site_admin

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


def _check_access(context, user, request):
    return     is_admin_or_content_admin_or_site_admin(user) \
            or has_permission(ACT_CONTENT_EDIT, context, request)


@component.adapter(ICompletionContext)
@interface.implementer(IExternalMappingDecorator)
class _CompletionContextAdminDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the :class:`ICompletionContext` with appropriate links for admins.
    """

    def _predicate(self, context, unused_result):
        return self._is_authenticated \
           and _check_access(context, self.remoteUser, self.request)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context,
                    rel=COMPLETION_POLICY_VIEW_NAME,
                    elements=('@@%s' % COMPLETION_POLICY_VIEW_NAME,))
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        _links.append(link)


@component.adapter(ICompletionContext)
@interface.implementer(IExternalMappingDecorator)
class _CompletionContextSettingsDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the :class:`ICompletionContext` with appropriate links for admins.
    """

    def _predicate(self, context, unused_result):
        completion_policy = ICompletionContextCompletionPolicyContainer(context)
        return self._is_authenticated \
           and completion_policy.context_policy is not None \
           and _check_access(context, self.remoteUser, self.request)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        for name in (COMPLETION_REQUIRED_VIEW_NAME,
                     COMPLETION_NOT_REQUIRED_VIEW_NAME,
                     DEFAULT_REQUIRED_POLICY_PATH_NAME):
            link = Link(context,
                        rel=name,
                        elements=('@@%s' % name,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)


@component.adapter(ICompletableItem)
@interface.implementer(IExternalMappingDecorator)
class CompletableItemDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the :class:`ICompletableItem` with requirement information. This
    requires being able to adapt :class:`ICompletableItem` to the correct
    :class:`ICompletionContext`.
    """

    def __init__(self, context, request):
        super(CompletableItemDecorator, self).__init__(context, request)
        self.context = context

    @Lazy
    def completion_context(self):
        return ICompletionContext(self.context, None)

    def _predicate(self, unused_context, unused_result):
        completion_policy = ICompletionContextCompletionPolicyContainer(self.completion_context,
                                                                        None)
        return self._is_authenticated \
           and self.completion_context is not None \
           and completion_policy is not None \
           and completion_policy.context_policy is not None

    def _do_decorate_external(self, context, result):
        required_container = ICompletableItemContainer(self.completion_context)
        default_policy = ICompletableItemDefaultRequiredPolicy(self.completion_context)
        is_required = required_container.is_item_required(context)
        is_not_required = required_container.is_item_optional(context)
        default_state = not is_required and not is_not_required
        if default_state:
            item_mime_type = getattr(context, 'mime_type', '')
            is_required = item_mime_type in default_policy.mime_types
        result['CompletionRequired'] = is_required
        # We're default if we are not explicitly required/not-required
        result['CompletionDefaultState'] = default_state
