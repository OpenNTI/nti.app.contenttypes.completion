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

from nti.contenttypes.completion.completion import CompletedItem

from nti.contenttypes.completion.index import install_completed_item_catalog

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.dataserver.metadata.index import get_metadata_catalog

from nti.metadata import queue_add

generation = 2

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

        lsm = ds_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)
        install_completed_item_catalog(ds_folder, intids)

        metadata = get_metadata_catalog()
        intids = metadata['mimeType'].apply(
            {'any_of': (CompletedItem.mimeType,)}
        )
        for doc_id in intids or ():
            queue_add(doc_id)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Contenttype completion evolution %s done.', generation)


def evolve(context):
    """
    Evolve to gen 2 by indexing the completed items
    """
    do_evolve(context)
