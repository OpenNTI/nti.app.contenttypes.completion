#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=inherit-non-class,expression-not-assigned

from zope import interface

from nti.schema.field import Object

from nti.contenttypes.completion.interfaces import ICompletionContext

from nti.dataserver.interfaces import IACLProvider
from nti.dataserver.interfaces import IEnumerableEntityContainer
from nti.dataserver.interfaces import IUser


class ICompletionContextContained(interface.Interface):

    completion_context = Object(ICompletionContext,
                                title=u"The completion context this progress is context is rooted",
                                required=True)


class ICompletedItemsContext(ICompletionContextContained):

    user = Object(IUser,
                  title=u'The user we are scoped to',
                  required=False)


class ICompletionContextUserProgress(ICompletionContextContained):
    """
    A representation of a particular users progress
    in a ICompletionContext
    """
    user = Object(IUser,
                  title=u'The user we are scoped to',
                  required=False)


class ICompletionContextACLProvider(IACLProvider):
    """
    An ACL provider giving permissions beneath an ICompletionContext.
    Typically adapted from (ICompletionContext, *)
    """


class ICompletionContextCohort(IEnumerableEntityContainer):
    """
    An entity container that is treated as a cohort when aggregating
    completion information or listing completion details
    """
