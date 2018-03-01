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

from requests.structures import CaseInsensitiveDict

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.completion.views import COMPLETION_REQUIRED_VIEW_NAME
from nti.app.contenttypes.completion.views import COMPLETION_NOT_REQUIRED_VIEW_NAME

from nti.app.contenttypes.completion.views import raise_error
from nti.app.contenttypes.completion.views import MessageFactory as _

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.contenttypes.completion.interfaces import ICompletionContext
from nti.contenttypes.completion.interfaces import ICompletableItemContainer

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

from nti.ntiids.ntiids import find_object_with_ntiid

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


class AbstractCompletionRequiredView(AbstractAuthenticatedView):

    @property
    def completable_container(self):
        return ICompletableItemContainer(self.completion_context)

    @property
    def completion_context(self):
        return self.context

    @property
    def item_ntiid(self):
        # Get the sub path ntiid if we're drilling in.
        return self.request.subpath[0] if self.request.subpath else ''


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICompletionContext,
             name=COMPLETION_REQUIRED_VIEW_NAME,
             permission=nauth.ACT_UPDATE,
             request_method='GET')
class CompletionRequiredView(AbstractCompletionRequiredView):
    """
    A view to fetch the :class:`ICompletableItem` required keys for our
    :class:`ICompletionContext`.
    """

    def __call__(self):
        result = LocatedExternalDict()
        required_keys = self.completable_container.get_required_keys()
        result[ITEMS] = required_keys
        result[TOTAL] = result[ITEM_COUNT] = len(required_keys)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICompletionContext,
             name=COMPLETION_NOT_REQUIRED_VIEW_NAME,
             permission=nauth.ACT_UPDATE,
             request_method='GET')
class CompletionNotRequiredView(AbstractCompletionRequiredView):
    """
    A view to fetch the :class:`ICompletableItem` not-required keys for our
    :class:`ICompletionContext`.
    """

    def __call__(self):
        result = LocatedExternalDict()
        optional_keys = self.completable_container.get_optional_keys()
        result[ITEMS] = optional_keys
        result[TOTAL] = result[ITEM_COUNT] = len(optional_keys)
        return result


class AbstractRequiredUpdateView(AbstractCompletionRequiredView,
                                 ModeledContentUploadRequestUtilsMixin):

    LOG_MESSAGE = ''

    def _update_container(self, key):
        raise NotImplementedError()

    def _get_keys(self):
        raise NotImplementedError()

    def _get_item(self):
        key = None
        item_json = self.readInput()
        factory = find_factory_for(item_json)
        if factory is not None:
            item = factory()
            update_from_external_object(item, item_json)
            key = getattr(item, 'ntiid', '')
            if not key:
                raise_error({'message': _(u"Completable item does not have ntiid."),
                             'code': 'ItemWithoutNTIIDError'})
        else:
            values = CaseInsensitiveDict(item_json)
            key = values.get('ntiid')
        if not key:
            raise_error({'message': _(u"No ntiid given for completion requirement update."),
                         'code': 'NoNTIIDGivenError'})
        item = find_object_with_ntiid(key)
        if item is None:
            logger.warn('Completable item not found with ntiid (%s)', key)
            raise_error({'message': _(u"Object not found for ntiid."),
                         'code': 'CompletableItemNotFoundError'})
        logger.info('Adding key to completion %s container for context.', self.LOG_MESSAGE)
        return item

    def _do_call(self):
        item = self._get_item()
        self._update_container(item)
        result = LocatedExternalDict()
        keys = self._get_keys()
        result[ITEMS] = keys
        result[TOTAL] = result[ITEM_COUNT] = len(keys)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICompletionContext,
             name=COMPLETION_REQUIRED_VIEW_NAME,
             permission=nauth.ACT_UPDATE,
             request_method='PUT')
class CompletionRequiredUpdateView(AbstractRequiredUpdateView):
    """
    A view to set an item that is required for the :class:`ICompletionContext`.
    """

    LOG_MESSAGE = 'required'

    def _update_container(self, item):
        # The interface will make sure this element only exists in either
        # required or optional.
        return self.completable_container.add_required_item(item)

    def _get_keys(self):
        return self.completable_container.get_required_keys()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICompletionContext,
             name=COMPLETION_NOT_REQUIRED_VIEW_NAME,
             permission=nauth.ACT_UPDATE,
             request_method='PUT')
class CompletionNotRequiredUpdateView(AbstractRequiredUpdateView):
    """
    A view to set an item that is not required for the
    :class:`ICompletionContext`.
    """

    LOG_MESSAGE = 'not required'

    def _update_container(self, item):
        # The interface will make sure this element only exists in either
        # required or optional.
        return self.completable_container.add_optional_item(item)

    def _get_keys(self):
        return self.completable_container.get_optional_keys()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICompletionContext,
             name=COMPLETION_REQUIRED_VIEW_NAME,
             permission=nauth.ACT_UPDATE,
             request_method='DELETE')
class CompletionRequiredDeleteView(AbstractCompletionRequiredView):


    def __call__(self):
        item_ntiid = self.item_ntiid
        self.completable_container.remove_required_item(item_ntiid)
        logger.info('Item no longer required for completion %s', item_ntiid)
        return hexc.HTTPNoContent()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICompletionContext,
             name=COMPLETION_NOT_REQUIRED_VIEW_NAME,
             permission=nauth.ACT_UPDATE,
             request_method='DELETE')
class CompletionNotRequiredDeleteView(AbstractCompletionRequiredView):


    def __call__(self):
        item_ntiid = self.item_ntiid
        self.completable_container.remove_optional_item(item_ntiid)
        logger.info('Item no longer not-required for completion %s', item_ntiid)
        return hexc.HTTPNoContent()
