#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from datetime import datetime

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from requests.structures import CaseInsensitiveDict

from zope import component

from zope.cachedescriptors.property import Lazy

from zope.security.interfaces import IPrincipal

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.completion.catalog import get_completion_contexts
from nti.app.contenttypes.completion.catalog import rebuild_completed_items_catalog

from nti.app.contenttypes.completion.interfaces import ICompletedItemsContext
from nti.app.contenttypes.completion.interfaces import IAwardedCompletedItemsContext
from nti.app.contenttypes.completion.interfaces import ICompletionContextCohort

from nti.app.contenttypes.completion.views import BUILD_COMPLETION_VIEW
from nti.app.contenttypes.completion.views import RESET_COMPLETION_VIEW
from nti.app.contenttypes.completion.views import USER_DATA_COMPLETION_VIEW
from nti.app.contenttypes.completion.views import raise_error
from nti.app.contenttypes.completion.views import MessageFactory as _

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.common.string import is_true

from nti.contenttypes.completion.completion import AwardedCompletedItem

from nti.contenttypes.completion.interfaces import ICompletedItemContainer
from nti.contenttypes.completion.interfaces import ICompletableItemProvider
from nti.contenttypes.completion.interfaces import IPrincipalCompletedItemContainer
from nti.contenttypes.completion.interfaces import IPrincipalAwardedCompletedItemContainer
from nti.contenttypes.completion.interfaces import ICompletableItem

from nti.contenttypes.completion.utils import update_completion
from nti.contenttypes.completion.utils import get_completable_items_for_user
from nti.contenttypes.completion.utils import get_required_completable_items_for_user

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import is_course_instructor

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import is_admin_or_site_admin

from nti.dataserver.interfaces import IDataserverFolder

from nti.dataserver.users.users import User

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.links.links import Link

from nti.ntiids.ntiids import find_object_with_ntiid


ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
MIMETYPE = StandardExternalFields.MIMETYPE
ITEM_COUNT = StandardExternalFields.ITEM_COUNT
CLASS = StandardExternalFields.CLASS
LINKS = StandardExternalFields.LINKS

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
             request_method='POST')
class AwardCompletedItemView(AbstractAuthenticatedView,
                             ModeledContentUploadRequestUtilsMixin):
    """
    A view that allows course admins to manually award a completable item
    as completed, moving it into the user's IPrincipalAwardedCompletedItemContainer
    """
    
    DEFAULT_FACTORY_MIMETYPE = "application/vnd.nextthought.completion.awardedcompleteditem"

    def readInput(self, value=None):
        if self.request.body:
            values = super(AwardCompletedItemView, self).readInput(value)
        else:
            values = self.request.params
        values = dict(values)
        # Can't be CaseInsensitive with internalization
        if MIMETYPE not in values:
            values[MIMETYPE] = self.DEFAULT_FACTORY_MIMETYPE
        values['Item'] = self._get_item_for_key(values['completable_ntiid'])
        values['Principal'] = self.context.user
        values['CompletedDate'] = datetime.utcnow()
        values['awarder'] = User.get_user(self.request.remote_user)
        if not 'Success' in values:
            values['Success'] = True
        return values
    
    @Lazy
    def _course(self):
        return ICourseInstance(self.context.completion_context)
    
    def _get_item_for_key(self, key):
        item = find_object_with_ntiid(key)
        if item is None:
            logger.warn('Completable item not found with ntiid (%s)', key)
            raise_error({'message': _(u"Object not found for ntiid."),
                         'code': 'CompletableItemNotFoundError'})
        if not ICompletableItem.providedBy(item):
            logger.warn('Item is not ICompletableItem (%s)', key)
            raise_error({'message': _(u"Item is not completable.."),
                         'code': 'InvalidCompletableItemError'})
        return item
    
    #Only course instructors, site admins, and NT admins should be able to manually award completables
    def _check_access(self):
        if      not is_admin_or_site_admin(self.remoteUser) \
                and not is_course_instructor(self._course, self.remoteUser):
                raise hexc.HTTPForbidden()
    
    def __call__(self):
        self._check_access()
        
        user = self.context.user
        
        user_awarded_container = component.getMultiAdapter((user, self.context.completion_context),
                                                   IPrincipalAwardedCompletedItemContainer)
        
        
        try:
            completable_ntiid = self.request.json_body['completable_ntiid']
            completable = self._get_item_for_key(completable_ntiid)
        except KeyError: 
            raise hexc.HTTPBadRequest("Must POST json with 'completable_ntiid' key")
        '''
        try:
            awarded_reason = self.request.json_body['reason']
        except KeyError:
            awarded_reason = ''
        
        awarded_completed_item = AwardedCompletedItem(Principal=user,
                                                      Item=completable,
                                                      CompletedDate=datetime.utcnow(),
                                                      awarder=User.get_user(self.request.remote_user),
                                                      reason=awarded_reason)
        '''
        awarded_item = self.readCreateUpdateContentObject(self.remoteUser)
        
        if 'force' in self.request.params:
            force_overwrite = self.request.params['force']
        else:
            force_overwrite = False
        
        if completable_ntiid in user_awarded_container:
            if force_overwrite:
                user_awarded_container.remove_item(completable)
            else:
            # Provide links to overwrite (force flag) or refresh on conflict.
                links = []
                link = Link(self.request.path, rel=u'overwrite',
                            params={u'force': True}, method=u'POST')
                links.append(link)
                raise_json_error(
                    self.request,
                    hexc.HTTPConflict,
                    {
                        CLASS: 'DestructiveChallenge',
                        'message': _(u'This item has already been awarded complete.'),
                        'code': 'ContentVersionConflictError',
                        LINKS: to_external_object(links),
                        MIMETYPE: 'application/vnd.nextthought.destructivechallenge'
                    },
                    None)
        
        user_awarded_container.add_completed_item(awarded_item)
        return awarded_item
