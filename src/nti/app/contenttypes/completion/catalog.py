#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from ZODB.POSException import POSError

from zope import component

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.dataserver.metadata.index import get_metadata_catalog

from nti.contenttypes.completion.index import get_completed_item_catalog

from nti.contenttypes.completion.interfaces import get_completables
from nti.contenttypes.completion.interfaces import ICompletionContext
from nti.contenttypes.completion.interfaces import ICompletedItemContainer

from nti.site.hostpolicy import get_all_host_sites

logger = __import__('logging').getLogger(__name__)


def get_completion_contexts():
    for obj in get_completables():
        if ICompletionContext.providedBy(obj):
            yield obj


def get_completed_items(context):
    # pylint: disable=too-many-function-args
    container = ICompletedItemContainer(context)
    for user_container in list(container.values()):  # by definition
        for value in list(user_container.values()):  # by definition
            yield value


def rebuild_completed_items_catalog(seen=None, metadata=True):
    catalog = get_completed_item_catalog()
    for index in catalog.values():
        index.clear()
    # reindex
    items = dict()
    contexts = set()
    seen = set() if seen is None else seen
    metadata_catalog = get_metadata_catalog()
    intids = component.getUtility(IIntIds)
    for host_site in get_all_host_sites():  # check all sites
        with current_site(host_site):
            count = 0
            for context in get_completion_contexts():
                doc_id = intids.queryId(context)
                if doc_id is None or doc_id in contexts:
                    continue
                contexts.add(doc_id)
                for item in get_completed_items(context):
                    doc_id = intids.queryId(item)
                    if doc_id is None or doc_id in seen:
                        continue
                    try:
                        seen.add(doc_id)
                        catalog.index_doc(doc_id, item)
                        if metadata:
                            metadata_catalog.index_doc(doc_id, item)
                    except POSError:
                        logger.error("Error while indexing object %s/%s",
                                     doc_id, type(item))
                    else:
                        count += 1
            logger.info("%s object(s) indexed in site %s",
                        count, host_site.__name__)
            items[host_site.__name__] = count
    return items
