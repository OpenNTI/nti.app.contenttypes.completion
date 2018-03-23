#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from collections import Counter

import math

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from zope import interface
from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.completion.adapters import CompletionContextProgressFactory

from nti.app.contenttypes.completion.interfaces import ICompletionContextProgress
from nti.app.contenttypes.completion.interfaces import ICompletionContextUserProgress
from nti.app.contenttypes.completion.interfaces import ICompletionContextCohort

from nti.app.contenttypes.completion.views import MessageFactory as _

from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy
from nti.contenttypes.completion.interfaces import ICompletableItemCompletionPolicy
from nti.contenttypes.completion.interfaces import IProgress

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IPrincipal

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)

@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET')
class ProgressContextView(AbstractAuthenticatedView):

    @Lazy
    def completion_context_policy(self):
        return ICompletionContextCompletionPolicy(self.context.completion_context, None)

    @view_config(permission=nauth.ACT_READ,
                 context=ICompletionContextProgress)
    def aggegate_stats(self):
        if self.completion_context_policy is None:
            raise hexc.HTTPNotFound()

        bucket_size = self.request.params.get('bucketSize', 5)

        cohort = ICompletionContextCohort(self.context.completion_context, ())
        total_students = 0
        accumulated_progress = 0
        count_started = 0
        count_completed = 0
        distribution = Counter()

        for user in cohort:
            progress = component.queryMultiAdapter((user, self.context.completion_context), IProgress)
            if progress.MaxPossibleProgress:
                percentage_complete = float(progress.AbsoluteProgress) / float(progress.MaxPossibleProgress)
            else:
                percentage_complete = 0
            bucketed = bucket_size * math.floor(percentage_complete * 100 / bucket_size)
            distribution[bucketed] += 1
            accumulated_progress += percentage_complete

            if progress.AbsoluteProgress:
                count_started += 1
            if progress.Completed:
                count_completed += 1
            total_students += 1

        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context

        result['MaxPossibleProgress'] = total_students
        result['AbsoluteProgress'] = accumulated_progress
        result['PercentageProgress'] = accumulated_progress / total_students if total_students else 0.0
        result['TotalUsers'] = total_students
        result['CountHasProgress'] = count_started
        result['CountCompleted'] = count_completed
        result['ProgressDistribution'] = {k/100.0: distribution[k]
                                          for k in range(0, 101, bucket_size)}
           
        return result


    @view_config(permission=nauth.ACT_READ,
                 context=ICompletionContextUserProgress)
    def user_progress(self):
        if self.context.user is None:
            raise hexc.HTTPNotFound()
        if self.completion_context_policy is None:
            raise hexc.HTTPNotFound()
        progress = component.queryMultiAdapter((self.context.user, self.context.completion_context), IProgress)
        return progress if progress is not None else hexc.HTTPNoContent()


    @view_config(permission=nauth.ACT_READ,
                 context=ICompletionContextUserProgress,
                 name="details")
    def user_progress_details(self):
        if self.context.user is None:
            raise hexc.HTTPNotFound()
        if self.completion_context_policy is None:
            raise hexc.HTTPNotFound()
        progress = component.queryMultiAdapter((self.context.user, self.context.completion_context), IProgress)

        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context

        result['ContextProgress'] = progress

        items = {}

        progress_factory = CompletionContextProgressFactory(self.context.user, self.context.completion_context)

        completable = progress_factory.completable_items
        for key in completable:
            item = completable[key]
            item_progress = component.queryMultiAdapter((self.context.user, item, self.context.completion_context),
                                                        IProgress)
            item_policy = component.getMultiAdapter((item, self.context.completion_context),
                                                    ICompletableItemCompletionPolicy)
            if item_progress is not None:
                ext_progress  = to_external_object(item_progress)

                completed_item = progress_factory.user_completed_items[key]
                ext_progress['_IndexCompletedDate'] = completed_item.CompletedDate if completed_item else None

                completed_item = item_policy.is_complete(item_progress)
                ext_progress['_CalculatedCompletedDate'] = completed_item.CompletedDate if completed_item else None
                item_progress = ext_progress
                                                                            
            items[key] = item_progress

        result[ITEMS] = items
        return result
        

    @view_config(permission=nauth.ACT_LIST,
                 context=ICompletionContextUserProgress,
                 name='list')
    def list_users(self):
        """
        This is probably really expensive.  Adapt the completion context
        to an IEntityEnumerable
        """
        if self.context.user is not None:
            raise hexc.HTTPNotFound()
        if self.completion_context_policy is None:
            raise hexc.HTTPNotFound()
        
        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context

        # We could support subsets (e.g. course scopes, groups, etc)
        # by adding a layer of indirection here that was able to produce
        # ICompletionContextCohorts for a given name provided as a query param
        users = ICompletionContextCohort(self.context.completion_context, ())
        items = {}
        for user in users:
            items[IPrincipal(user).id] = component.queryMultiAdapter((user,
                                                                      self.context.completion_context),
                                                                     IProgress)
        result[ITEMS] = items
        result[TOTAL] = result[ITEM_COUNT] = len(items)
        return result
