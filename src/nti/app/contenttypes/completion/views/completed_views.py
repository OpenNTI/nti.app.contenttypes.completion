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

from zope import interface

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.completion.adapters import CompletionContextProgressFactory

from nti.app.contenttypes.completion.interfaces import ICompletedItemsContext

from nti.app.contenttypes.completion.views import MessageFactory as _

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)

@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICompletedItemsContext,
             permission=nauth.ACT_READ,
             request_method='GET')
class UserCompletedItems(AbstractAuthenticatedView):

    @property
    def user(self):
        return self.context.user

    @property
    def completion_context(self):
        return self.context.completion_context
    
    def __call__(self):
        if self.user is None:
            raise hexc.HTTPNotFound()
        completion_builder = CompletionContextProgressFactory(self.user, self.completion_context)

        results = LocatedExternalDict()
        results.__name__ = self.user.username
        results.__parent__ = self.context

        items = {itemid: getattr(completion_builder.user_completed_items.get(itemid), 'CompletedDate', None)
                 for itemid in completion_builder.completable_items}

        results[ITEMS] = items
        results[TOTAL] = results[ITEM_COUNT] = len(items)
        results['Username'] = self.user.username
        
        return results

        

        
