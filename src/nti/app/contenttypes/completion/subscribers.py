#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from zope.component.hooks import getSite

from zope.lifecycleevent.interfaces import IObjectRemovedEvent

from zope.security.management import queryInteraction

from nti.contenttypes.completion.interfaces import ICompletableItem
from nti.contenttypes.completion.interfaces import ICompletionContext
from nti.contenttypes.completion.interfaces import ICompletedItemContainer

from nti.contenttypes.completion.utils import get_indexed_completed_items

from nti.coremetadata.interfaces import IUser

from nti.site.interfaces import IHostPolicyFolder

logger = __import__('logging').getLogger(__name__)


@component.adapter(IUser, IObjectRemovedEvent)
def _on_user_deleted(user, unused_event=None):
    """
    When a user is deleted delete its completed items.
    This should be done after all progress events have been fired.
    """
    logger.info("Removing completed items data for user %s", user)
    username = user.username
    items = get_indexed_completed_items((username,))
    # get completed item containers
    contexts = {ICompletionContext(x, None) for x in items}
    containers = {ICompletedItemContainer(x, None) for x in contexts}
    containers.discard(None)
    # remove user data
    for container in containers:
        container.remove_principal(username)


@component.adapter(ICompletableItem, IObjectRemovedEvent)
def _on_completable_item_deleted(item, unused_event=None):
    """
    When a completable item is deleted delete its completed items
    """
    # We don't want to remove any items during a sync
    if queryInteraction() is not None:
        logger.info("Removing completed items data for %s", item)
        site = IHostPolicyFolder(item, None) or getSite()
        items = get_indexed_completed_items(items=(item.ntiid,),
                                            sites=(site.__name__,))
        # get completed item containers
        contexts = {ICompletionContext(x, None) for x in items}
        containers = {ICompletedItemContainer(x, None) for x in contexts}
        containers.discard(None)
        # remove item data
        for container in containers:
            container.remove_item(item)
