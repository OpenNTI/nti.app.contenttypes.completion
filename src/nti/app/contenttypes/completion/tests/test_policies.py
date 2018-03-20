#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import not_none
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains_inanyorder

from zope import interface

from nti.app.contenttypes.completion import COMPLETION_PATH_NAME
from nti.app.contenttypes.completion import COMPLETION_POLICY_VIEW_NAME
from nti.app.contenttypes.completion import DEFAULT_REQUIRED_POLICY_PATH_NAME

from nti.app.contenttypes.completion.tests import CompletionTestLayer

from nti.app.contenttypes.completion.tests.models import PersistentCompletionContext

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contenttypes.completion.policies import CompletableItemAggregateCompletionPolicy

from nti.coremetadata.interfaces import IContained

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users import User

from nti.externalization.externalization import StandardExternalFields

from nti.ntiids.oids import to_external_ntiid_oid

ITEMS = StandardExternalFields.ITEMS
CREATED_TIME = StandardExternalFields.CREATED_TIME
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED


class TestCompletionPolicyViews(ApplicationLayerTest):

    layer = CompletionTestLayer

    aggregate_mimetype = CompletableItemAggregateCompletionPolicy.mime_type

    def _set_context_policy(self, context_ntiid):
        full_data = {u'MimeType': self.aggregate_mimetype}

        context_url = '/dataserver2/Objects/%s' % context_ntiid
        context_res = self.testapp.get(context_url).json_body
        self.require_link_href_with_rel(context_res,
                                        COMPLETION_POLICY_VIEW_NAME)

        url = '/dataserver2/Objects/%s/%s/%s' % (context_ntiid,
                                                 COMPLETION_PATH_NAME,
                                                 COMPLETION_POLICY_VIEW_NAME)
        return self.testapp.put_json(url, full_data)

    def _get_completion_policy(self, context_ntiid):
        url = '/dataserver2/Objects/%s/%s/%s' % (context_ntiid,
                                                 COMPLETION_PATH_NAME,
                                                 COMPLETION_POLICY_VIEW_NAME)
        return self.testapp.get(url)

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    def test_completion_policy(self):
        """
        Test setting/retrieving a completion policy.
        """
        admin_username = 'sjohnson@nextthought.com'
        non_admin_username = 'non_admin'
        with mock_dataserver.mock_db_trans(self.ds):
            completion_context = PersistentCompletionContext()
            completion_context.containerId = 'container_id'
            interface.alsoProvides(completion_context, IContained)
            self._create_user(non_admin_username)
            user = User.get_user(admin_username)
            user.addContainedObject(completion_context)
            context_ntiid = to_external_ntiid_oid(completion_context)
        assert_that(context_ntiid, not_none())

        non_admin_environ = self._make_extra_environ(non_admin_username)

        full_data = {u'MimeType': self.aggregate_mimetype}

        # Empty
        url = '/dataserver2/Objects/%s/%s/%s' % (context_ntiid,
                                                 COMPLETION_PATH_NAME,
                                                 COMPLETION_POLICY_VIEW_NAME)
        self.testapp.get(url, status=404)
        self.testapp.get(url, extra_environ=non_admin_environ, status=403)

        # Update
        res = self._set_context_policy(context_ntiid)
        res = res.json_body
        policy_href = res['href']
        last_last_mod = res[LAST_MODIFIED]
        assert_that(res[CREATED_TIME], not_none())
        assert_that(last_last_mod, not_none())
        assert_that(res['percentage'], is_(1.0))
        assert_that(policy_href, not_none())

        # Put
        res = self.testapp.put_json(policy_href, {'percentage': .5})
        res = res.json_body
        assert_that(res[CREATED_TIME], not_none())
        assert_that(res[LAST_MODIFIED], not_none())
        assert_that(res[LAST_MODIFIED], is_not(last_last_mod))
        last_last_mod = res[LAST_MODIFIED]
        assert_that(res['percentage'], is_(.5))
        assert_that(policy_href, not_none())

        # Get
        res = self.testapp.get(url)
        res = res.json_body
        assert_that(res[CREATED_TIME], not_none())
        assert_that(res[LAST_MODIFIED], not_none())
        assert_that(res[LAST_MODIFIED], is_(last_last_mod))
        assert_that(res['percentage'], is_(.5))
        assert_that(policy_href, not_none())

        # Validation
        self.testapp.put_json(policy_href, {'percentage': 1.5}, status=422)
        self.testapp.put_json(policy_href, {'percentage': -.5}, status=422)
        self.testapp.put_json(policy_href, {'percentage': None}, status=422)
        self.testapp.put_json(policy_href, {'percentage': 1.0})

        self.testapp.put_json(url, full_data,
                              extra_environ=non_admin_environ,
                              status=403)
        self.testapp.put_json(policy_href, {'percentage': .5},
                              extra_environ=non_admin_environ,
                              status=403)

        # Update sub-policy
        sub_item_ntiid1 = 'item_ntiid1'
        sub_url = '%s/%s' % (url, sub_item_ntiid1)
        self.testapp.get(sub_url, status=404)
        self.testapp.get(sub_url, extra_environ=non_admin_environ, status=403)

        # Update
        res = self.testapp.put_json(sub_url, full_data)
        res = res.json_body
        sub_policy_href = res['href']
        last_last_mod = res[LAST_MODIFIED]
        assert_that(res[CREATED_TIME], not_none())
        assert_that(last_last_mod, not_none())
        assert_that(res['percentage'], is_(1.0))
        assert_that(sub_policy_href, not_none())

        assert_that(sub_policy_href, is_not(policy_href))

        # Put
        res = self.testapp.put_json(sub_policy_href, {'percentage': .5})
        res = res.json_body
        assert_that(res['percentage'], is_(.5))

        res = self.testapp.get(sub_url)
        res = res.json_body
        assert_that(res['percentage'], is_(.5))

        res = self.testapp.get(url)
        res = res.json_body
        assert_that(res['percentage'], is_(1.0))

        self.testapp.get(sub_url, extra_environ=non_admin_environ, status=403)

        # Delete
        self.testapp.delete(sub_url)
        self.testapp.delete(url)

        self.testapp.get(sub_url, status=404)
        self.testapp.get(url, status=404)

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    def test_default_required_policy(self):
        """
        Test updating the default required policy.
        """
        admin_username = 'sjohnson@nextthought.com'
        non_admin_username = 'non_admin'
        with mock_dataserver.mock_db_trans(self.ds):
            completion_context = PersistentCompletionContext()
            completion_context.containerId = 'container_id'
            interface.alsoProvides(completion_context, IContained)
            self._create_user(non_admin_username)
            user = User.get_user(admin_username)
            user.addContainedObject(completion_context)
            context_ntiid = to_external_ntiid_oid(completion_context)
        assert_that(context_ntiid, not_none())

        non_admin_environ = self._make_extra_environ(non_admin_username)

        self._set_context_policy(context_ntiid)
        policy_res = self._get_completion_policy(context_ntiid).json_body
        self.require_link_href_with_rel(policy_res,
                                        DEFAULT_REQUIRED_POLICY_PATH_NAME)

        url = '/dataserver2/Objects/%s/%s/%s' % (context_ntiid,
                                                 COMPLETION_PATH_NAME,
                                                 DEFAULT_REQUIRED_POLICY_PATH_NAME)

        # Empty
        self.testapp.get(url, extra_environ=non_admin_environ, status=403)
        res = self.testapp.get(url)
        res = res.json_body
        assert_that(res['mime_types'], has_length(0))

        # Update
        self.testapp.put_json(url,
                              {'mime_types': ['mimetype1', 'mimetype2']})
        res = self.testapp.get(url)
        res = res.json_body
        mime_types = res['mime_types']
        assert_that(mime_types, has_length(2))
        assert_that(mime_types, contains_inanyorder('mimetype1', 'mimetype2'))

        # Empty out
        self.testapp.put_json(url, {'mime_types': []})
        res = self.testapp.get(url)
        res = res.json_body
        mime_types = res['mime_types']
        assert_that(mime_types, has_length(0))
