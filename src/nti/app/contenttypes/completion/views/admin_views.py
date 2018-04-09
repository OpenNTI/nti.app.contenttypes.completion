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

from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.completion.interfaces import ICompletedItemsContext
from nti.app.contenttypes.completion.interfaces import ICompletionContextCohort

from nti.app.contenttypes.completion.views import BUILD_COMPLETION_VIEW
from nti.app.contenttypes.completion.views import USER_DATA_COMPLETION_VIEW

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.common.string import is_true

from nti.contenttypes.completion.interfaces import ICompletableItemProvider
from nti.contenttypes.completion.interfaces import IPrincipalCompletedItemContainer

from nti.contenttypes.completion.utils import update_completion
from nti.contenttypes.completion.utils import get_completable_items_for_user
from nti.contenttypes.completion.utils import get_required_completable_items_for_user

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
             name=BUILD_COMPLETION_VIEW,
             permission=nauth.ACT_NTI_ADMIN,
             request_method='POST')
class BuildCompletionDataView(AbstractAuthenticatedView,
                              ModeledContentUploadRequestUtilsMixin):
    """
    A view to build completion data for a :class:`ICompletionContext`.
    """

    def readInput(self, value=None):
        if self.request.body:
            values = super(BuildCompletionDataView, self).readInput(value)
        else:
            values = self.request.params
        return CaseInsensitiveDict(values)

    @Lazy
    def _params(self):
        return self.readInput()

    @property
    def reset_completed(self):
        default = False
        param = self._params.get('reset') \
            or  self._params.get('reset_completed') \
            or  self._params.get('ResetCompleted')
        result = is_true(param) if param else default
        return result

    @Lazy
    def users(self):
        if self.context.user is not None:
            result = (self.context.user,)
        else:
            result = ICompletionContextCohort(self.context.completion_context, ())
        return result

    def do_reset_completed(self):
        logger.info('Clearing user completed item containers')
        for user in self.users:
            user_container = component.getMultiAdapter((user, self.context.completion_context),
                                                       IPrincipalCompletedItemContainer)
            user_container.clear()

    def build_completion_data(self, user, completable_items):
        for item in completable_items:
            update_completion(item, item.ntiid, user,
                              self.context.completion_context)

    def __call__(self):
        if self.reset_completed:
            self.do_reset_completed()
        item_providers = None
        item_count = 0
        logger.info('Building completion data')
        for user in self.users:
            # Attempt to re-use providers, which may have internal caching
            if item_providers is None:
                item_providers = component.subscribers((self.context.completion_context,),
                                                       ICompletableItemProvider)
            completable_items = set()
            for item_provider in item_providers:
                completable_items.update(item_provider.iter_items(user))

            # Close enough
            item_count = item_count or len(completable_items)
            self.build_completion_data(user, completable_items)
        logger.info('Finished building completion data for %s users (items=~%s)',
                    len(self.users),
                    item_count)

        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        result[ITEM_COUNT] = item_count
        result['UserCount'] = len(self.users)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICompletedItemsContext,
             name=USER_DATA_COMPLETION_VIEW,
             permission=nauth.ACT_NTI_ADMIN,
             request_method='GET')
class UserCompletionDataView(AbstractAuthenticatedView):
    """
    An admin view useful for debugging a particular user's completion
    data.
    """

    def __call__(self):
        user = self.context.user
        if user is None:
            raise hexc.HTTPNotFound()
        completable_items = get_completable_items_for_user(user,
                                                           self.context.completion_context)
        required_items = get_required_completable_items_for_user(user,
                                                                 self.context.completion_context)
        completable_ntiids = set(x.ntiid for x in completable_items)
        required_ntiids = set(x.ntiid for x in required_items)
        optional_ntiids = completable_ntiids - required_ntiids
        user_container = component.getMultiAdapter((user, self.context.completion_context),
                                                   IPrincipalCompletedItemContainer)
        completed_ntiids = set(user_container)

        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        result['CompletedItems'] = sorted(completed_ntiids)
        result['CompletedRequiredItems'] = sorted(completed_ntiids & required_ntiids)
        result['CompletedOptionalItems'] = sorted(completed_ntiids & optional_ntiids)
        result['IncompleteRequiredItems'] = sorted(required_ntiids - completed_ntiids)
        result['CompletableItems'] = sorted(completable_ntiids)
        result['RequiredItems'] = sorted(required_ntiids)
        result['OptionalItems'] = sorted(optional_ntiids)
        return result

