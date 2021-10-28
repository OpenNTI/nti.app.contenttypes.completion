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
from pyramid.view import view_defaults

from requests.structures import CaseInsensitiveDict

from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.completion.catalog import get_completion_contexts
from nti.app.contenttypes.completion.catalog import rebuild_completed_items_catalog

from nti.app.contenttypes.completion.interfaces import ICompletedItemsContext
from nti.app.contenttypes.completion.interfaces import IAwardedCompletedItemsContext
from nti.app.contenttypes.completion.interfaces import ICompletionContextCohort

from nti.app.contenttypes.completion.views import BUILD_COMPLETION_VIEW
from nti.app.contenttypes.completion.views import RESET_COMPLETION_VIEW
from nti.app.contenttypes.completion.views import USER_DATA_COMPLETION_VIEW
from nti.app.contenttypes.completion.views import AWARDED_COMPLETED_ITEMS_PATH_NAME
from nti.app.contenttypes.completion.views import CompletableItemsPathAdapter

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.common.string import is_true

from nti.contenttypes.completion.interfaces import ICompletedItemContainer
from nti.contenttypes.completion.interfaces import ICompletableItemProvider
from nti.contenttypes.completion.interfaces import IPrincipalCompletedItemContainer

from nti.contenttypes.completion.utils import update_completion
from nti.contenttypes.completion.utils import get_completable_items_for_user
from nti.contenttypes.completion.utils import get_required_completable_items_for_user

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IDataserverFolder

from nti.dataserver.users.users import User

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


@view_config(context=IDataserverFolder)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               permission=nauth.ACT_NTI_ADMIN,
               name='RebuildCompletedItemsCatalog')
class RebuildCompletedItemsCatalogView(AbstractAuthenticatedView):

    def __call__(self):
        seen = set()
        items = rebuild_completed_items_catalog(seen)
        result = LocatedExternalDict()
        result[ITEMS] = items
        result[ITEM_COUNT] = result[TOTAL] = len(seen)
        return result


@view_config(context=IDataserverFolder)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               permission=nauth.ACT_NTI_ADMIN,
               name='RemoveGhostCompletedItemContainers')
class RemoveGhostCompletedItemContainersView(AbstractAuthenticatedView):

    def __call__(self):
        result = LocatedExternalDict()
        result[ITEMS] = items = set()
        for context in get_completion_contexts():
            container = ICompletedItemContainer(context)
            # pylint: disable=too-many-function-args
            for username, user_container in list(container.items()):
                if User.get_user(username) is None:
                    items.add(username)
                    user_container.clear()
        result[ITEMS] = sorted(items)
        result[ITEM_COUNT] = result[TOTAL] = len(items)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICompletedItemsContext,
             name=RESET_COMPLETION_VIEW,
             permission=nauth.ACT_NTI_ADMIN,
             request_method='POST')
class ResetCompletionDataView(AbstractAuthenticatedView,
                              ModeledContentUploadRequestUtilsMixin):
    """
    A view to remove completion data for a :class:`ICompletionContext`;
    probably only useful for testing purposes since we do not turn around
    and rebuild data.
    """

    def readInput(self, value=None):
        if self.request.body:
            values = super(ResetCompletionDataView, self).readInput(value)
        else:
            values = self.request.params
        return CaseInsensitiveDict(values)

    @Lazy
    def _params(self):
        return self.readInput()

    @Lazy
    def users(self):
        # pylint: disable=no-member
        if self.context.user is not None:
            result = (self.context.user,)
        else:
            result = ICompletionContextCohort(self.context.completion_context, ())
        return result

    def do_reset_completed(self):
        # pylint: disable=no-member,not-an-iterable
        logger.info('Clearing user completed item containers')
        for user in self.users:
            user_container = component.getMultiAdapter((user, self.context.completion_context),
                                                       IPrincipalCompletedItemContainer)
            user_container.clear()

    def __call__(self):
        self.do_reset_completed()
        return hexc.HTTPNoContent()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICompletedItemsContext,
             name=BUILD_COMPLETION_VIEW,
             permission=nauth.ACT_NTI_ADMIN,
             request_method='POST')
class BuildCompletionDataView(ResetCompletionDataView):
    """
    A view to build completion data for a :class:`ICompletionContext`,
    optionally resetting completed data.
    """

    @property
    def reset_completed(self):
        default = False
        # pylint: disable=no-member
        param = self._params.get('reset') \
             or self._params.get('reset_completed') \
             or self._params.get('ResetCompleted')
        result = is_true(param) if param else default
        return result

    def build_completion_data(self, user, completable_items):
        for item in completable_items:
            # pylint: disable=no-member
            update_completion(item, item.ntiid, user,
                              self.context.completion_context)

    def __call__(self):
        if self.reset_completed:
            self.do_reset_completed()
        item_providers = None
        item_count = 0
        user_count = 0
        logger.info('Building completion data')
        # pylint: disable=no-member,not-an-iterable
        for user in self.users:
            user_count += 1
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
                    user_count,
                    item_count)

        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        result[ITEM_COUNT] = item_count
        result['UserCount'] = user_count
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
        # pylint: disable=no-member
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
    
    
@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IAwardedCompletedItemsContext,
             name=AWARDED_COMPLETED_ITEMS_PATH_NAME,
             permission=nauth.ACT_CONTENT_EDIT,
             request_method='POST')
class AwardCompletedItemView(AbstractAuthenticatedView):
    """
    A view that allows course admins to manually award a completable item
    as completed, moving it into the user's IPrincipalAwardedCompletedItemContainer
    """
    
    def __call__(self):
        from IPython.terminal.debugger import set_trace;set_trace()
        result = LocatedExternalDict()
        return result
