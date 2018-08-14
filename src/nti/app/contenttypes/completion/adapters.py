#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite

from nti.coremetadata.interfaces import IUser

from nti.contenttypes.completion.interfaces import IProgress
from nti.contenttypes.completion.interfaces import ISiteAdapter
from nti.contenttypes.completion.interfaces import ICompletedItem
from nti.contenttypes.completion.interfaces import ICompletionContext
from nti.contenttypes.completion.interfaces import ICompletedItemProvider
from nti.contenttypes.completion.interfaces import IRequiredCompletableItemProvider
from nti.contenttypes.completion.interfaces import IPrincipalCompletedItemContainer
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy

from nti.contenttypes.completion.progress import CompletionContextProgress

from nti.ntiids.oids import to_external_ntiid_oid

from nti.traversal.traversal import find_interface

from nti.site.interfaces import IHostPolicyFolder

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICompletedItemProvider)
@component.adapter(IUser, ICompletionContext)
class PrincipalCompletedItemsProvider(object):
    """
    Provides the :class:`ICompletedItem`s from the users completed items container
    """

    def __init__(self, user, context):
        self.user = user
        self.context = context

    @property
    def user_completed_items(self):
        return component.getMultiAdapter((self.user, self.context),
                                         IPrincipalCompletedItemContainer)

    def completed_items(self):
        for item in self.user_completed_items.itervalues():
            yield item

    @property
    def last_modified(self):
        return self.user_completed_items.lastModified


class CompletionContextProgressFactory(object):
    """
    Returns the :class:`ICompletionContextProgress` for an :class:`ICompletionContext`.
    """

    def __init__(self, user, context, required_item_providers=None):
        self.user = user
        self.context = context
        self._required_item_providers = required_item_providers

    @Lazy
    def required_item_providers(self):
        result = self._required_item_providers
        if not result:
            result = component.subscribers((self.context,),
                                           IRequiredCompletableItemProvider)
        return result

    @Lazy
    def completable_items(self):
        """
        A map of ntiid to required completable items.
        """
        result = {}
        # pylint: disable=not-an-iterable
        for completable_provider in self.required_item_providers:
            for item in completable_provider.iter_items(self.user):
                result[item.ntiid] = item
        return result

    @Lazy
    def user_completed_items(self):
        """
        A map of ntiid to all user completed items.
        """
        result = {}
        for completed_provider in component.subscribers((self.user, self.context),
                                                        ICompletedItemProvider):
            for item in completed_provider.completed_items():
                result[item.item_ntiid] = item
        return result

    @Lazy
    def user_required_completed_items(self):
        """
        A map of ntiid to all user completed items that only includes the
        completed items that are required.
        """
        result = {}
        # pylint: disable=not-an-iterable,unsupported-membership-test
        for required_ntiid in self.completable_items:
            if required_ntiid in self.user_completed_items:
                # pylint: disable=unsubscriptable-object
                result[required_ntiid] = self.user_completed_items[required_ntiid]
        return result

    def _get_last_mod(self):
        if self.user_required_completed_items:
            # pylint: disable=no-member
            return max(x.CompletedDate for x in self.user_required_completed_items.values())

    def __call__(self):
        ntiid = getattr(self.context, 'ntiid', '') \
             or to_external_ntiid_oid(self.context)
        last_mod = self._get_last_mod()
        completed_count = len(self.user_required_completed_items)
        max_possible = len(self.completable_items)
        has_progress = bool(completed_count)
        # We probably always want to return this progress, even if there is
        # none.
        progress = CompletionContextProgress(NTIID=ntiid,
                                             AbsoluteProgress=completed_count,
                                             MaxPossibleProgress=max_possible,
                                             LastModified=last_mod,
                                             Item=self.context,
                                             User=self.user,
                                             CompletionContext=self.context,
                                             HasProgress=has_progress)

        policy = ICompletionContextCompletionPolicy(self.context, None)
        if policy is not None:
            completed_item = policy.is_complete(progress)
            progress.CompletedItem = completed_item
        return progress


@component.adapter(IUser, ICompletionContext)
@interface.implementer(IProgress)
def _completion_context_progress(user, context):
    return CompletionContextProgressFactory(user, context)()


@component.adapter(ICompletedItem)
@interface.implementer(IHostPolicyFolder)
def _completed_item_to_site(item):
    return find_interface(item, IHostPolicyFolder, strict=False)


# catalog


class _Site(object):

    __slots__ = ('site',)

    def __init__(self, site):
        self.site = site


@component.adapter(ICompletedItem)
@interface.implementer(ISiteAdapter)
def _completed_item_to_siteadapter(item):
    site = IHostPolicyFolder(item, None)
    site = getSite() if site is None else site
    return _Site(site.__name__) if site is not None else None
