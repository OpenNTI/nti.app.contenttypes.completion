#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.completion.interfaces import ICompletedItemsContext

from nti.contenttypes.completion.authorization import ACT_VIEW_PROGRESS

from nti.contenttypes.completion.interfaces import ICompletedItemProvider

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICompletedItemsContext,
             permission=ACT_VIEW_PROGRESS,
             request_method='GET')
class UserCompletedItems(AbstractAuthenticatedView):

    @property
    def user(self):
        return self.context.user

    @property
    def completion_context(self):
        return self.context.completion_context

    @Lazy
    def providers(self):
        return tuple(component.subscribers((self.user, self.completion_context),
                                            ICompletedItemProvider))

    def _get_last_mod(self):
        last_mod = None
        for provider in self.providers:
            if provider.last_modified is not None:
                if last_mod is not None:
                    last_mod = max(last_mod, provider.last_modified)
                else:
                    last_mod = provider.last_modified
        return last_mod

    def __call__(self):
        if self.user is None:
            raise hexc.HTTPNotFound()

        results = LocatedExternalDict()
        results.__name__ = self.user.username
        results.__parent__ = self.context

        items = {}
        for provider in self.providers:
            for completed_item in provider.completed_items():
                items[completed_item.item_ntiid] = completed_item.CompletedDate

        results[ITEMS] = items
        results[TOTAL] = results[ITEM_COUNT] = len(items)
        results['Username'] = self.user.username
        self.request.response.last_modified = self._get_last_mod()
        return results
