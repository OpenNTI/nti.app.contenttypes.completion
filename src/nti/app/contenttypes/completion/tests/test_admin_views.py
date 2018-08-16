#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_
from hamcrest import contains
from hamcrest import not_none
from hamcrest import has_length
from hamcrest import assert_that

from datetime import datetime

from zope import interface
from zope import component

from nti.app.contenttypes.completion import COMPLETION_PATH_NAME
from nti.app.contenttypes.completion import BUILD_COMPLETION_VIEW
from nti.app.contenttypes.completion import RESET_COMPLETION_VIEW
from nti.app.contenttypes.completion import USER_DATA_COMPLETION_VIEW
from nti.app.contenttypes.completion import COMPLETED_ITEMS_PATH_NAME

from nti.app.contenttypes.completion.tests import CompletionTestLayer

from nti.app.contenttypes.completion.tests.models import PersistentCompletableItem
from nti.app.contenttypes.completion.tests.models import PersistentCompletionContext

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contenttypes.completion.completion import CompletedItem

from nti.contenttypes.completion.interfaces import ICompletionContext
from nti.contenttypes.completion.interfaces import IPrincipalCompletedItemContainer

from nti.coremetadata.interfaces import IContained

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users import User

from nti.externalization.externalization import StandardExternalFields

from nti.ntiids.oids import to_external_ntiid_oid

TOTAL = StandardExternalFields.TOTAL
ITEMS = StandardExternalFields.ITEMS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


class TestAdminViews(ApplicationLayerTest):

    layer = CompletionTestLayer

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    def test_admin_views(self):
        """
        Test admin views to fetch user completion data as well as building that data.
        """
        now = datetime.utcnow()
        admin_username = 'sjohnson@nextthought.com'
        user1_username = 'user1_username'
        user2_username = 'user2_username'
        with mock_dataserver.mock_db_trans(self.ds):
            user1 = self._create_user(user1_username)
            self._create_user(user2_username)
            completion_context = PersistentCompletionContext()
            item1 = PersistentCompletableItem('ntiid1')
            item2 = PersistentCompletableItem('ntiid2')
            completion_context.containerId = 'container_id'
            item1.containerId = 'container_id'
            item2.containerId = 'container_id'
            interface.alsoProvides(completion_context, IContained)
            user = User.get_user(admin_username)
            for item in (completion_context, item1, item2):
                user.addContainedObject(item)
            context_ntiid = to_external_ntiid_oid(completion_context)
            item_ntiid1 = to_external_ntiid_oid(item1)
            item1.ntiid = item_ntiid1
            item_ntiid2 = to_external_ntiid_oid(item2)
            item2.ntiid = item_ntiid2

            # Add completed item
            user_container = component.queryMultiAdapter((user1, completion_context),
                                                         IPrincipalCompletedItemContainer)
            completed_item1 = CompletedItem(Principal=user1,
                                            Item=item1,
                                            CompletedDate=now)
            user_container.add_completed_item(completed_item1)

        assert_that(context_ntiid, not_none())

        # User stats
        root_url = '/dataserver2/Objects/%s/%s/%s' % (context_ntiid,
                                                      COMPLETION_PATH_NAME,
                                                      COMPLETED_ITEMS_PATH_NAME)
        user1_stats_url = '%s/users/%s/@@%s' % (root_url,
                                                user1_username,
                                                USER_DATA_COMPLETION_VIEW)
        user2_stats_url = '%s/users/%s/@@%s' % (root_url,
                                                user2_username,
                                                USER_DATA_COMPLETION_VIEW)

        res = self.testapp.get(user1_stats_url).json_body
        assert_that(res['CompletableItems'], has_length(0))
        assert_that(res['CompletedItems'], has_length(1))
        assert_that(res['CompletedItems'], contains(item_ntiid1))
        assert_that(res['CompletedOptionalItems'], has_length(0))
        assert_that(res['CompletedRequiredItems'], has_length(0))
        assert_that(res['IncompleteRequiredItems'], has_length(0))

        res = self.testapp.get(user2_stats_url).json_body
        assert_that(res['CompletableItems'], has_length(0))
        assert_that(res['CompletedItems'], has_length(0))
        assert_that(res['CompletedOptionalItems'], has_length(0))
        assert_that(res['CompletedRequiredItems'], has_length(0))
        assert_that(res['IncompleteRequiredItems'], has_length(0))

        # Build data
        build_url = '/dataserver2/Objects/%s/%s/%s/@@%s' % (context_ntiid,
                                                            COMPLETION_PATH_NAME,
                                                            COMPLETED_ITEMS_PATH_NAME,
                                                            BUILD_COMPLETION_VIEW)
        user1_build_url = '/dataserver2/Objects/%s/%s/%s/%s/%s/@@%s' % (context_ntiid,
                                                                        COMPLETION_PATH_NAME,
                                                                        COMPLETED_ITEMS_PATH_NAME,
                                                                        'users',
                                                                        user1_username,
                                                                        BUILD_COMPLETION_VIEW)
        user2_build_url = '/dataserver2/Objects/%s/%s/%s/%s/%s/@@%s' % (context_ntiid,
                                                                        COMPLETION_PATH_NAME,
                                                                        COMPLETED_ITEMS_PATH_NAME,
                                                                        'users',
                                                                        user2_username,
                                                                        BUILD_COMPLETION_VIEW)

        res = self.testapp.post(build_url)
        res = res.json_body
        assert_that(res['UserCount'], is_(0))
        assert_that(res[ITEM_COUNT], is_(0))

        res = self.testapp.get(user1_stats_url).json_body
        assert_that(res['CompletedItems'], has_length(1))
        assert_that(res['CompletedItems'], contains(item_ntiid1))

        res = self.testapp.get(user2_stats_url).json_body
        assert_that(res['CompletedItems'], has_length(0))

        # For user
        res = self.testapp.post(user1_build_url).json_body
        assert_that(res['UserCount'], is_(1))
        assert_that(res[ITEM_COUNT], is_(0))

        res = self.testapp.post(user2_build_url).json_body
        assert_that(res['UserCount'], is_(1))
        assert_that(res[ITEM_COUNT], is_(0))

        # Nothing changes
        res = self.testapp.get(user1_stats_url).json_body
        assert_that(res['CompletedItems'], has_length(1))
        assert_that(res['CompletedItems'], contains(item_ntiid1))

        res = self.testapp.get(user2_stats_url).json_body
        assert_that(res['CompletedItems'], has_length(0))

        # For user with reset
        res = self.testapp.post_json(user2_build_url, {"reset": True}).json_body
        assert_that(res['UserCount'], is_(1))
        assert_that(res[ITEM_COUNT], is_(0))

        res = self.testapp.get(user1_stats_url).json_body
        assert_that(res['CompletedItems'], has_length(1))
        assert_that(res['CompletedItems'], contains(item_ntiid1))

        res = self.testapp.get(user2_stats_url).json_body
        assert_that(res['CompletedItems'], has_length(0))

        # Now reset user 1
        res = self.testapp.post_json(user1_build_url, {"reset": True}).json_body
        assert_that(res['UserCount'], is_(1))
        assert_that(res[ITEM_COUNT], is_(0))

        res = self.testapp.get(user1_stats_url).json_body
        assert_that(res['CompletedItems'], has_length(0))

        res = self.testapp.get(user2_stats_url).json_body
        assert_that(res['CompletedItems'], has_length(0))

        # Test reset view
        reset_url = '/dataserver2/Objects/%s/%s/%s/@@%s' % (context_ntiid,
                                                            COMPLETION_PATH_NAME,
                                                            COMPLETED_ITEMS_PATH_NAME,
                                                            RESET_COMPLETION_VIEW)
        user1_reset_url = '/dataserver2/Objects/%s/%s/%s/%s/%s/@@%s' % (context_ntiid,
                                                                        COMPLETION_PATH_NAME,
                                                                        COMPLETED_ITEMS_PATH_NAME,
                                                                        'users',
                                                                        user1_username,
                                                                        RESET_COMPLETION_VIEW)
        user2_reset_url = '/dataserver2/Objects/%s/%s/%s/%s/%s/@@%s' % (context_ntiid,
                                                                        COMPLETION_PATH_NAME,
                                                                        COMPLETED_ITEMS_PATH_NAME,
                                                                        'users',
                                                                        user2_username,
                                                                        RESET_COMPLETION_VIEW)

        with mock_dataserver.mock_db_trans(self.ds):
            user1 = User.get_user(user1_username)
            # Add completed item
            user_container = component.queryMultiAdapter((user1, completion_context),
                                                         IPrincipalCompletedItemContainer)
            completed_item1 = CompletedItem(Principal=user1,
                                            Item=item1,
                                            CompletedDate=now)
            user_container.add_completed_item(completed_item1)
            
            context = ICompletionContext(completed_item1, None)
            assert_that(context, is_(not_none()))

        self.testapp.post_json(user2_reset_url)
        res = self.testapp.get(user1_stats_url).json_body
        assert_that(res['CompletedItems'], has_length(1))

        self.testapp.post_json(user1_reset_url)
        res = self.testapp.get(user1_stats_url).json_body
        assert_that(res['CompletedItems'], has_length(0))

        self.testapp.post_json(reset_url)
        res = self.testapp.get(user1_stats_url).json_body
        assert_that(res['CompletedItems'], has_length(0))
