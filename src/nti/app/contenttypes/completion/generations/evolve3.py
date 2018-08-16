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

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from nti.contenttypes.completion.index import IX_PRINCIPAL
from nti.contenttypes.completion.index import get_completed_item_catalog

from nti.contenttypes.completion.interfaces import ICompletedItem
from nti.contenttypes.completion.interfaces import ICompletionContext

from nti.contenttypes.completion.subscribers import completion_context_deleted_event

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.dataserver.users.users import User

generation = 3

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IDataserver)
class MockDataserver(object):

    root = None

    def get_by_oid(self, oid, ignore_creator=False):
        resolver = component.queryUtility(IOIDResolver)
        if resolver is None:
            logger.warning("Using dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
        return None


def do_evolve(context):
    setHooks()
    conn = context.connection
    root = conn.root()
    ds_folder = root['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)

    with site(ds_folder):
        assert component.getSiteManager() == ds_folder.getSiteManager(), \
               "Hooks not installed?"

        count = 0
        contexts = set()
        lsm = ds_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)
        catalog = get_completed_item_catalog()
        index = catalog[IX_PRINCIPAL]

        # check all the users in index
        values_to_documents = index.values_to_documents
        for username in tuple(values_to_documents.keys()):
            user = User.get_entity(username)
            if IUser.providedBy(user):
                continue
            logger.info("Removing completed item(s) for deleted user %s",
                        username)
            for doc_id in tuple(values_to_documents.get(username) or ()):
                obj = intids.queryObject(doc_id)
                if ICompletedItem.providedBy(obj):
                    intids.unregister(obj)
                    contexts.add(ICompletionContext(obj, None))
                else:
                    catalog.unindex_doc(doc_id)
                count += 1

        # check invalid contexts
        contexts.discard(None)
        for context in tuple(contexts):
            doc_id = intids.queryId(context)
            if doc_id is None:  # deleted context i.e. course
                completion_context_deleted_event(context)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Contenttype completion evolution %s done. %s record(s) unindexed',
                generation, count)


def evolve(context):
    """
    Evolve to gen 3 by unindexing completed items for deleted users
    """
    do_evolve(context)
