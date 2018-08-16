#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from nti.contenttypes.completion.interfaces import ICompletionContext
from nti.contenttypes.completion.interfaces import ICompletedItemContainer

from nti.contenttypes.completion.utils import get_indexed_completed_items

from nti.coremetadata.interfaces import IUser

from nti.dataserver.users.interfaces import IWillDeleteEntityEvent

logger = __import__('logging').getLogger(__name__)


@component.adapter(IUser, IWillDeleteEntityEvent)
def _on_user_deleted(user, unused_event=None):
    """
    When a user is deleted delete its completed items
    """
    logger.info("Removing completed items data for user %s", user)
    username = user.username
    items = get_indexed_completed_items((username,))
    contexts = {ICompletionContext(x, None) for x in items}
    containers = {ICompletedItemContainer(x) for x in contexts}
    containers.discard(None)
    for container in containers:
        container.remove_principal(username)
