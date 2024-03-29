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

from nti.app.contenttypes.completion import COMPLETION_PATH_NAME
from nti.app.contenttypes.completion import COMPLETION_POLICY_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETABLE_ITEMS_PATH_NAME
from nti.app.contenttypes.completion import COMPLETION_REQUIRED_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETION_NOT_REQUIRED_VIEW_NAME
from nti.app.contenttypes.completion import DEFAULT_REQUIRED_POLICY_PATH_NAME
from nti.app.contenttypes.completion import AWARDED_COMPLETED_ITEMS_PATH_NAME
from nti.app.contenttypes.completion import DELETE_AWARDED_COMPLETED_ITEM_VIEW

from nti.app.renderers.decorators import AbstractRequestAwareDecorator
from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.completion.authorization import ACT_VIEW_PROGRESS
from nti.contenttypes.completion.authorization import ACT_AWARD_PROGRESS

from nti.contenttypes.completion.interfaces import ICompletableItem
from nti.contenttypes.completion.interfaces import IAwardedCompletedItem
from nti.contenttypes.completion.interfaces import ICompletionContext
from nti.contenttypes.completion.interfaces import ICompletionSubContext
from nti.contenttypes.completion.interfaces import ICompletionContextProvider
from nti.contenttypes.completion.interfaces import ICompletableItemContainer
from nti.contenttypes.completion.interfaces import ICompletableItemCompletionPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy
from nti.contenttypes.completion.interfaces import ICompletableItemDefaultRequiredPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicyConfigurationUtility

from nti.contenttypes.completion.utils import get_completed_item
from nti.contenttypes.completion.utils import get_awarded_completed_item

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.authorization import is_admin_or_content_admin

from nti.dataserver.interfaces import IUser

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.singleton import Singleton

from nti.links.links import Link

from nti.traversal.traversal import find_interface

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


def _check_access(context, user, request):
    return     is_admin_or_content_admin(user) \
            or has_permission(ACT_CONTENT_EDIT, context, request)


@component.adapter(ICompletionContext)
@interface.implementer(IExternalMappingDecorator)
class _ContextCompletionPolicy(Singleton):
    """
    Decorates :class:`ICompletionContextCompletionPolicy`
    """

    def decorateExternalMapping(self, context, mapping):
        mapping['CompletionPolicy'] = ICompletionContextCompletionPolicy(context,
                                                                         None)


@component.adapter(ICompletionContext)
@interface.implementer(IExternalMappingDecorator)
class _CompletionContextAdminDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the :class:`ICompletionContext` with appropriate links for admins.
    """

    def _predicate(self, context, unused_result):
        return self._is_authenticated \
           and _check_access(context, self.remoteUser, self.request)

    def _make_completion_policy_link(self, context, rel, method):
        link = Link(context,
                    rel=rel,
                    elements=(COMPLETION_PATH_NAME,
                              '@@%s' % COMPLETION_POLICY_VIEW_NAME,),
                    method=method)
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        return link

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        _links.append(self._make_completion_policy_link(context, COMPLETION_POLICY_VIEW_NAME, 'GET'))

        config = component.getUtility(ICompletionContextCompletionPolicyConfigurationUtility)
        if config.can_edit_completion_policy(context):
            _links.append(self._make_completion_policy_link(context, 'UpdateCompletionPolicy', 'PUT'))
            _links.append(self._make_completion_policy_link(context, 'ResetCompletionPolicy', 'DELETE'))


@component.adapter(ICompletionContextCompletionPolicy)
@interface.implementer(IExternalMappingDecorator)
class _CompletionContextSettingsDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the :class:`ICompletionContextCompletionPolicy` with appropriate
    links for admins.
    """

    def _predicate(self, context, unused_result):
        completion_context = find_interface(context, ICompletionContext)
        completion_policy = ICompletionContextCompletionPolicy(completion_context,
                                                               None)
        return self._is_authenticated \
           and completion_policy is not None \
           and _check_access(context, self.remoteUser, self.request)

    def _make_default_required_link(self, context, rel, method):
        link = Link(context,
                    rel=rel,
                    elements=(COMPLETION_PATH_NAME,
                              '%s' % DEFAULT_REQUIRED_POLICY_PATH_NAME,),
                    method=method)
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        return link

    def _do_decorate_external(self, context, result):
        context = find_interface(context, ICompletionContext)
        _links = result.setdefault(LINKS, [])
        for name in (COMPLETION_REQUIRED_VIEW_NAME,
                     COMPLETION_NOT_REQUIRED_VIEW_NAME):
            link = Link(context,
                        rel=name,
                        elements=(COMPLETION_PATH_NAME,
                                  COMPLETABLE_ITEMS_PATH_NAME,
                                  '@@%s' % name,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)

        _links.append(self._make_default_required_link(context, 'GetDefaultRequiredPolicy', 'GET'))

        # TODO: Why is this not an edit link on the required policy?
        if not ICompletionSubContext.providedBy(context):
            _links.append(self._make_default_required_link(context, 'UpdateDefaultRequiredPolicy', 'PUT'))


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

    def get_completion_context(self, item):
        """
        We shouldn't use the self.context for getting the provider,
        because there is a derived decorator AssetCompletableItemDecorator,
        in which self.context is not a ICompletableItem
        """
        provider =  ICompletionContextProvider(item, None)
        return provider() if provider else None

    def has_completion_policy(self, completion_context):
        completion_policy = ICompletionContextCompletionPolicy(completion_context,
                                                               None)
        return completion_policy is not None

    def _do_decorate_external(self, context, result):
        completion_context = self.get_completion_context(context)
        if self.has_completion_policy(completion_context):
            required_container = ICompletableItemContainer(completion_context)
            default_policy = ICompletableItemDefaultRequiredPolicy(completion_context)
            is_required = required_container.is_item_required(context)
            is_not_required = required_container.is_item_optional(context)
            # We're default if we are not explicitly required/not-required
            is_default_state = not is_required and not is_not_required
            item_mime_type = getattr(context, 'mime_type', '')
            default_required_state = item_mime_type in default_policy.mime_types
            if is_default_state:
                is_required = default_required_state
            result['CompletionRequired'] = is_required
            result['CompletionDefaultState'] = default_required_state
            result['IsCompletionDefaultState'] = is_default_state

        if completion_context is not None:
            # See if we have a user from our request context
            # If so, and it is not ourselves, that means we are another user
            # viewing a user's progress; that user *must* have the ACT_VIEW_PROGRESS
            # permission then.
            user = IUser(self.request.context, self.remoteUser)
            if     user == self.remoteUser \
                or has_permission(ACT_VIEW_PROGRESS, self.request.context, self.request):
                completed_item = get_completed_item(user,
                                                    completion_context,
                                                    context)
                result['CompletedItem'] = completed_item
                result['CompletedDate'] = getattr(completed_item, 'CompletedDate', None)
                awarded_item = get_awarded_completed_item(user, 
                                                          completion_context,
                                                          context)
                result['AwardedItem'] = awarded_item            


@component.adapter(ICompletableItem)
@interface.implementer(IExternalMappingDecorator)
class _CompletableItemCompletionPolicyDecorator(AbstractRequestAwareDecorator):

    def _completion_context(self, item):
        provider =  ICompletionContextProvider(item, None)
        return provider() if provider else None

    def _do_decorate_external(self, context, result):
        if not ICompletionContext.providedBy(context):
            result['CompletionPolicy'] = component.queryMultiAdapter((context, self._completion_context(context)),
                                                                     ICompletableItemCompletionPolicy)
