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

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.completion.views import MessageFactory as _

from nti.app.contenttypes.completion.views import CompletionContextPolicyPathAdapter

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.appserver.ugd_edit_views import UGDPutView

from nti.contenttypes.completion.interfaces import ICompletableItemCompletionPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicyContainer

from nti.dataserver import authorization as nauth

logger = __import__('logging').getLogger(__name__)


class AbstractCompletionContextPolicyView(AbstractAuthenticatedView):

    @property
    def completion_container(self):
        return ICompletionContextCompletionPolicyContainer(
                                        self.completion_context)

    @property
    def completion_context(self):
        return self.context.context


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=CompletionContextPolicyPathAdapter,
             permission=nauth.ACT_UPDATE,
             request_method='GET')
class CompletionContextPolicyView(AbstractCompletionContextPolicyView):
    """
    A view to fetch the :class:`ICompletableItemCompletionPolicy` for our
    :class:`ICompletionContext`.
    """

    def __call__(self):
        if self.completion_container.context_policy:
            return self.completion_container.context_policy
        raise hexc.HTTPNotFound()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=CompletionContextPolicyPathAdapter,
             permission=nauth.ACT_UPDATE,
             request_method='POST')
class CompletionContextPolicyPostView(AbstractCompletionContextPolicyView,
                                      ModeledContentUploadRequestUtilsMixin):
    """
    A view to set the :class:`ICompletableItemCompletionPolicy` for our
    :class:`ICompletionContext`.

    *subpath for ntiid -> container?
    """

    def _do_call(self):
        new_policy = self.readCreateUpdateContentObject(self.remoteUser)
        self.completion_container.context_policy = new_policy
        new_policy.__parent__ = self.completion_container
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

# FIXME
# subpath
