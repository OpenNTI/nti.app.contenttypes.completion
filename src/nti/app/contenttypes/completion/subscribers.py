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
from nti.coremetadata.interfaces import IMarkedForDeletion

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
    # FIXME: Why do we query this potentially large set?
    # Let's do so based on enrollment if we can. That might be a subscriber
    # order issue (use enrollment deletion if necessary).
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
        # Don't we just need the completion contexts?
        items = get_indexed_completed_items(items=(item.ntiid,),
                                            sites=(site.__name__,))
        # get completed item containers
        contexts = {ICompletionContext(x, None) for x in items}
        # We only need to individually remove items if their contexts
        # are not also being deleted. Deleting the contexts will clean
        # these containers anyway, much more efficiently.
        # Note: the subscriber to clean up a context's completed items
        # is not yet registered for all completion contexts (for some reason).
        contexts = {x for x in contexts if not IMarkedForDeletion.providedBy(x)}
        containers = {ICompletedItemContainer(x, None) for x in contexts}
        containers.discard(None)
        # remove item data
        for container in containers:
            container.remove_item(item)
