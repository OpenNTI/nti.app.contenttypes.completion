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

from nti.coremetadata.interfaces import IUser

from nti.contenttypes.completion.interfaces import IProgress
from nti.contenttypes.completion.interfaces import ICompletionContext
from nti.contenttypes.completion.interfaces import ICompletedItemProvider
from nti.contenttypes.completion.interfaces import IRequiredCompletableItemProvider
from nti.contenttypes.completion.interfaces import IPrincipalCompletedItemContainer
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy


from nti.contenttypes.completion.progress import CompletionContextProgress

from nti.ntiids.oids import to_external_ntiid_oid

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

    def completed_items(self):
        user_completed_items = component.queryMultiAdapter((self.user, self.context),
                                                           IPrincipalCompletedItemContainer)
        for item in user_completed_items.itervalues():
            yield item


class CompletionContextProgressFactory(object):
    """
    Returns the :class:`ICompletionContextProgress` for an :class:`ICompletionContext`.
    """

    def __init__(self, user, context):
        self.user = user
        self.context = context

    def _key(self, item):
        ntiid = getattr(item, 'ntiid', '')
        if not ntiid:
            ntiid = to_external_ntiid_oid(item)
        return ntiid

    @Lazy
    def completable_items(self):
        """
        A map of ntiid to required completable items.
        """
        result = {}
        for completable_provider in component.subscribers((self.user, self.context),
                                                          IRequiredCompletableItemProvider):
            for item in completable_provider.iter_items():
                key = self._key(item)
                result[key] = item
        return result

    @Lazy
    def user_completed_items(self):
        """
        A map of ntiid to user completed items. Only return items that are
        required for this context.
        """
        result = {}
        for completed_provider in component.subscribers((self.user, self.context),
                                                          ICompletedItemProvider):
            for item in completed_provider.completed_items():
                key = self._key(item.Item)
                if key in self.completable_items:
                    result[key] = item
        return result

    def _get_last_mod(self):
        if self.user_completed_items:
            return max(x.CompletedDate for x in self.user_completed_items.values())

    def __call__(self):
        ntiid = self._key(self.context)
        last_mod = self._get_last_mod()
        completed_count = len(self.user_completed_items)
        max_possible = len(self.completable_items)
        has_progress = bool(completed_count)
        # We probably always want to return this progress, even if there is none.
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
            if completed_item is not None:
                progress.Completed = True
                progress.CompletedDate = completed_item.CompletedDate
        return progress


@component.adapter(IUser, ICompletionContext)
@interface.implementer(IProgress)
def _completion_context_progress(user, context):
    return CompletionContextProgressFactory(user, context)()
