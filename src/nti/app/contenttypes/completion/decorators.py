#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: decorators.py 113814 2017-05-31 02:18:58Z josh.zuech $
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.location.interfaces import ILocation

from nti.app.contenttypes.completion import COMPLETION_POLICY_VIEW_NAME

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.completion.interfaces import ICompletionContext

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.authorization import is_admin_or_content_admin_or_site_admin

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


def _check_access(context, user, request):
    return     is_admin_or_content_admin_or_site_admin(user) \
            or has_permission(ACT_CONTENT_EDIT, context, request)


@component.adapter(ICompletionContext)
@interface.implementer(IExternalMappingDecorator)
class _CompletionContextAdminDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the :class:`ICompletionContext` with appropriate links for admins.
    """

    def _predicate(self, context, unused_result):
        return self._is_authenticated \
           and _check_access(context, self.remoteUser, self.request)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        for name in (COMPLETION_POLICY_VIEW_NAME,):
            link = Link(context,
                        rel=name,
                        elements=(name,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)
