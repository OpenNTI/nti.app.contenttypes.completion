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

from zope import interface

from zope.container.contained import Contained

from zope.traversing.interfaces import IPathAdapter

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.completion.views import COMPLETION_POLICY_VIEW_NAME
from nti.app.contenttypes.completion.views import DEFAULT_REQUIRED_POLICY_PATH_NAME

from nti.app.contenttypes.completion.views import CompletionPathAdapter

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.appserver.ugd_edit_views import UGDPutView

from nti.contenttypes.completion.interfaces import ICompletableItemCompletionPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy
from nti.contenttypes.completion.interfaces import ICompletableItemDefaultRequiredPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicyContainer

from nti.dataserver import authorization as nauth

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IPathAdapter)
class DefaultRequiredPolicyPathAdapter(Contained):

    __name__ = DEFAULT_REQUIRED_POLICY_PATH_NAME

    def __init__(self, context, request):
        # Context is our CompletionPathAdapter
        self.context = context
        self.completion_context = context.context
        self.request = request
        self.__parent__ = context


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=DefaultRequiredPolicyPathAdapter,
             permission=nauth.ACT_UPDATE,
             request_method='PUT')
class DefaultRequiredPolicyPutView(UGDPutView):
    """
    A view to update the :class:`ICompletableItemDefaultRequiredPolicy`.
    """

    def _get_object_to_update(self):
        # pylint: disable=no-member
        completion_context = self.context.completion_context
        return ICompletableItemDefaultRequiredPolicy(completion_context)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=DefaultRequiredPolicyPathAdapter,
             permission=nauth.ACT_UPDATE,
             request_method='GET')
class DefaultRequiredPolicyView(AbstractAuthenticatedView):
    """
    A view to fetch the :class:`ICompletableItemDefaultRequiredPolicy`.
    """

    def __call__(self):
        # pylint: disable=no-member
        completion_context = self.context.completion_context
        return ICompletableItemDefaultRequiredPolicy(completion_context)


class AbstractCompletionContextPolicyView(AbstractAuthenticatedView):

    @property
    def completion_container(self):
        return ICompletionContextCompletionPolicyContainer(
                                        self.completion_context)

    @property
    def completion_context(self):
        # pylint: disable=no-member
        return self.context.context

    @property
    def item_ntiid(self):
        # Get the sub path ntiid if we're drilling in.
        return self.request.subpath[0] if self.request.subpath else ''


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             name=COMPLETION_POLICY_VIEW_NAME,
             context=CompletionPathAdapter,
             permission=nauth.ACT_UPDATE,
             request_method='GET')
class CompletionContextPolicyView(AbstractCompletionContextPolicyView):
    """
    A view to fetch the :class:`ICompletableItemCompletionPolicy` for our
    :class:`ICompletionContext`.
    """

    def __call__(self):
        item_ntiid = self.item_ntiid
        if not item_ntiid:
            result = self.completion_container.context_policy
        else:
            result = self.completion_container.get(item_ntiid)

        if result is None:
            raise hexc.HTTPNotFound()
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=CompletionPathAdapter,
             name=COMPLETION_POLICY_VIEW_NAME,
             permission=nauth.ACT_UPDATE,
             request_method='PUT')
class CompletionContextPolicyUpdateView(AbstractCompletionContextPolicyView,
                                        ModeledContentUploadRequestUtilsMixin):
    """
    A view to set the :class:`ICompletableItemCompletionPolicy` for our
    :class:`ICompletionContext`.
    """

    def _do_call(self):
        new_policy = self.readCreateUpdateContentObject(self.remoteUser)
        item_ntiid = self.item_ntiid
        if not item_ntiid:
            self.completion_container.set_context_policy(new_policy)
        else:
            logger.info('Added completable policy for %s', item_ntiid)
            self.completion_container[item_ntiid] = new_policy
        return new_policy


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICompletableItemCompletionPolicy,
             permission=nauth.ACT_UPDATE,
             request_method='PUT')
class CompletionPolicyPutView(UGDPutView):
    """
    A view to update the :class:`ICompletableItemCompletionPolicy`.
    """

    def _get_object_to_update(self):
        return self.context


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             name=COMPLETION_POLICY_VIEW_NAME,
             context=CompletionPathAdapter,
             permission=nauth.ACT_UPDATE,
             request_method='DELETE')
class CompletionPolicyDeleteView(AbstractCompletionContextPolicyView):


    def __call__(self):
        item_ntiid = self.item_ntiid
        if     not item_ntiid \
            or item_ntiid == getattr(self.completion_context, 'ntiid', ''):
            self.completion_container.set_context_policy(None)
        else:
            try:
                del self.completion_container[item_ntiid]
                logger.info('Deleted completable policy for %s', item_ntiid)
            except KeyError:
                pass
        return hexc.HTTPNoContent()
