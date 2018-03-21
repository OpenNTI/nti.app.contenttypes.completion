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
from nti.contenttypes.completion.interfaces import ICompletableItemProvider
from nti.contenttypes.completion.interfaces import IPrincipalCompletedItemContainer

from nti.contenttypes.completion.progress import Progress

from nti.ntiids.oids import to_external_ntiid_oid

logger = __import__('logging').getLogger(__name__)


class CompletionContextProgress(object):
    """
    Returns the :class:`IProgress` for an :class:`ICompletionContext`.
    """

    def __init__(self, user, context):
        self.user = user
        self.context = context

    @Lazy
    def completable_items(self):
        """
        A map of ntiid to required completable items.
        """
        result = {}
        for completable_provider in component.subscribers((self.user, self.context),
                                                          ICompletableItemProvider):
            for item in completable_provider.iter_items():
                result[item.ntiid] = item
        return result

    @Lazy
    def user_completed_items(self):
        """
        A map of ntiid to user completed items. Only return items that are
        required for this context.
        """
        result = {}
        user_completed_items = component.queryMultiAdapter((self.user, self.context),
                                                           IPrincipalCompletedItemContainer)
        for key, completed_item in user_completed_items.items():
            if key in self.completable_items:
                result[key] = completed_item
        return user_completed_items

    def _get_last_mod(self):
        if self.user_completed_items:
            return max(x.CompletedDate for x in self.user_completed_items.values())

    def __call__(self):
        ntiid = getattr(self.context, 'ntiid', '')
        if not ntiid:
            ntiid = to_external_ntiid_oid(self.context)
        last_mod = self._get_last_mod()
        completed_count = len(self.user_completed_items)
        max_possible = len(self.completable_items)
        has_progress = bool(completed_count)
        # We probably always want to return this progress, even if there is none.
        progress = Progress(NTIID=ntiid,
                            AbsoluteProgress=completed_count,
                            MaxPossibleProgress=max_possible,
                            LastModified=last_mod,
                            Item=self.context,
                            User=self.user,
                            HasProgress=has_progress)
        return progress


@component.adapter(IUser, ICompletionContext)
@interface.implementer(IProgress)
def _completion_context_progress(user, context):
    return CompletionContextProgress(user, context)()
