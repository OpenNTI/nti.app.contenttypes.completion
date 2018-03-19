#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from zope import interface

from nti.app.contenttypes.completion.tests.interfaces import ITestPersistentCompletableItem
from nti.app.contenttypes.completion.tests.interfaces import ITestPersistentCompletionContext

from nti.contenttypes.completion.tests.test_models import MockCompletableItem
from nti.contenttypes.completion.tests.test_models import MockCompletionContext

from nti.coremetadata.mixins import ZContainedMixin

from nti.zodb.persistentproperty import PersistentPropertyHolder


@interface.implementer(ITestPersistentCompletionContext)
class PersistentCompletionContext(MockCompletionContext,
                                  PersistentPropertyHolder,
                                  ZContainedMixin):
    pass


@interface.implementer(ITestPersistentCompletableItem)
class PersistentCompletableItem(MockCompletableItem,
                                PersistentPropertyHolder,
                                ZContainedMixin):
    pass
