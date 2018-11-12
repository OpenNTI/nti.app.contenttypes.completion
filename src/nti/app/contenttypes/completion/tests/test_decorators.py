#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_
from hamcrest import is_not
from hamcrest import not_none
from hamcrest import has_key
from hamcrest import has_length
from hamcrest import assert_that

from zope import component
from zope import interface

from nti.app.contenttypes.completion.tests import CompletionTestLayer
from nti.app.contenttypes.completion.tests.models import PersistentCompletableItem
from nti.app.contenttypes.completion.tests.models import PersistentCompletionContext

from nti.app.contenttypes.completion.decorators import _CompletableItemCompletionPolicyDecorator

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.contenttypes.completion.interfaces import ICompletableItem
from nti.contenttypes.completion.interfaces import ICompletionContext

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.externalization.externalization import toExternalObject


class TestDecorators(ApplicationLayerTest):

    layer = CompletionTestLayer

    def _decorate(self, decorator, context):
        external = toExternalObject(context, decorate=False)
        decorator = decorator(context, None)
        decorator.decorateExternalMapping(context, external)
        return external

    @WithMockDSTrans
    def test_completable_item_completion_policy(self):
        context = PersistentCompletionContext()
        item = PersistentCompletableItem(u'ntiid1')
        def _content_provider(x):
            return context
        component.globalSiteManager.registerAdapter(_content_provider,
                                                    (ICompletableItem,),
                                                    ICompletionContext)

        external = self._decorate(_CompletableItemCompletionPolicyDecorator, item)
        assert_that(external, has_key('CompletionPolicy'))

        component.globalSiteManager.unregisterAdapter(_content_provider,
                                                      (ICompletableItem,),
                                                      ICompletionContext)
