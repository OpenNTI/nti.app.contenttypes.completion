#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_
from hamcrest import not_none
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains
from hamcrest import contains_inanyorder

from zope import interface

from nti.app.contenttypes.completion import COMPLETION_POLICY_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETION_REQUIRED_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETION_NOT_REQUIRED_VIEW_NAME

from nti.app.contenttypes.completion.tests import CompletionTestLayer

from nti.app.contenttypes.completion.tests.test_models import PersistentCompletableItem
from nti.app.contenttypes.completion.tests.test_models import PersistentCompletionContext

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contenttypes.completion.policies import CompletableItemAggregateCompletionPolicy

from nti.coremetadata.interfaces import IContained

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users import User

from nti.externalization.externalization import StandardExternalFields

from nti.ntiids.oids import to_external_ntiid_oid

TOTAL = StandardExternalFields.TOTAL
ITEMS = StandardExternalFields.ITEMS
CREATED_TIME = StandardExternalFields.CREATED_TIME
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED


class TestCompletableRequiredViews(ApplicationLayerTest):

    layer = CompletionTestLayer

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    def test_completable_required(self):
        """
        Test setting/retrieving a completion policy.
        """
        aggregate_mimetype = CompletableItemAggregateCompletionPolicy.mime_type
        admin_username = 'sjohnson@nextthought.com'
        non_admin_username = 'non_admin'
        with mock_dataserver.mock_db_trans(self.ds):
            completion_context = PersistentCompletionContext()
            item1 = PersistentCompletableItem('ntiid1')
            item2 = PersistentCompletableItem('ntiid2')
            completion_context.containerId = 'container_id'
            item1.containerId = 'container_id'
            item2.containerId = 'container_id'
            interface.alsoProvides(completion_context, IContained)
            self._create_user(non_admin_username)
            user = User.get_user(admin_username)
            for item in (completion_context, item1, item2):
                user.addContainedObject(item)
            context_ntiid = to_external_ntiid_oid(completion_context)
            item_ntiid1 = to_external_ntiid_oid(item1)
            item1.ntiid = item_ntiid1
            item_ntiid2 = to_external_ntiid_oid(item2)
            item2.ntiid = item_ntiid2
        assert_that(context_ntiid, not_none())

        non_admin_environ = self._make_extra_environ(non_admin_username)

        context_url = '/dataserver2/Objects/%s' % context_ntiid
        context_res = self.testapp.get(context_url).json_body
        self.forbid_link_with_rel(context_res,
                                  COMPLETION_REQUIRED_VIEW_NAME)
        self.forbid_link_with_rel(context_res,
                                  COMPLETION_NOT_REQUIRED_VIEW_NAME)

        # Set policy and now we have rels
        url = '/dataserver2/Objects/%s/%s' % (context_ntiid,
                                              COMPLETION_POLICY_VIEW_NAME)
        self.testapp.put_json(url, {u'MimeType': aggregate_mimetype})
        context_res = self.testapp.get(context_url).json_body
        self.require_link_href_with_rel(context_res,
                                        COMPLETION_REQUIRED_VIEW_NAME)
        self.require_link_href_with_rel(context_res,
                                        COMPLETION_NOT_REQUIRED_VIEW_NAME)


        required_url = '/dataserver2/Objects/%s/%s' % (context_ntiid,
                                                       COMPLETION_REQUIRED_VIEW_NAME)
        not_required_url = '/dataserver2/Objects/%s/%s' % (context_ntiid,
                                                           COMPLETION_NOT_REQUIRED_VIEW_NAME)

        # Empty
        res = self.testapp.get(required_url).json_body
        assert_that(res[ITEMS], has_length(0))

        res = self.testapp.get(not_required_url).json_body
        assert_that(res[ITEMS], has_length(0))

        self.testapp.get(required_url, extra_environ=non_admin_environ, status=403)
        self.testapp.get(not_required_url, extra_environ=non_admin_environ, status=403)

        # Bad data
        self.testapp.put_json(required_url, {u'ntiid': None}, status=422)
        self.testapp.put_json(required_url, {u'ntiid': '%sdne' % item_ntiid1}, status=422)

        # Update
        res = self.testapp.put_json(required_url, {u'ntiid': item_ntiid1})
        res = res.json_body
        assert_that(res[TOTAL], is_(1))
        assert_that(res[ITEMS], contains(item_ntiid1))

        res = self.testapp.get(not_required_url).json_body
        assert_that(res[ITEMS], has_length(0))

        res = self.testapp.put_json(not_required_url, {u'ntiid': item_ntiid2})
        res = res.json_body
        assert_that(res[TOTAL], is_(1))
        assert_that(res[ITEMS], contains(item_ntiid2))

        res = self.testapp.get(required_url).json_body
        assert_that(res[ITEMS], has_length(1))
        assert_that(res[ITEMS], contains(item_ntiid1))

        # Transfer
        res = self.testapp.put_json(not_required_url, {u'ntiid': item_ntiid1})
        res = res.json_body
        assert_that(res[TOTAL], is_(2))
        assert_that(res[ITEMS], contains_inanyorder(item_ntiid2, item_ntiid1))

        res = self.testapp.get(required_url).json_body
        assert_that(res[ITEMS], has_length(0))

        # Delete from empty container
        self.testapp.delete('%s/%s' % (required_url, item_ntiid1))
        self.testapp.delete('%s/%s' % (required_url, item_ntiid2))
        res = self.testapp.get(not_required_url).json_body
        assert_that(res[TOTAL], is_(2))
        assert_that(res[ITEMS], contains_inanyorder(item_ntiid2, item_ntiid1))

        # Delete
        self.testapp.delete('%s/%s' % (not_required_url, item_ntiid1))
        res = self.testapp.get(not_required_url).json_body
        assert_that(res[TOTAL], is_(1))
        assert_that(res[ITEMS], contains(item_ntiid2))

        res = self.testapp.get(required_url).json_body
        assert_that(res[ITEMS], has_length(0))

        self.testapp.delete('%s/%s' % (not_required_url, item_ntiid2))

        res = self.testapp.get(required_url).json_body
        assert_that(res[ITEMS], has_length(0))

        res = self.testapp.get(not_required_url).json_body
        assert_that(res[ITEMS], has_length(0))

