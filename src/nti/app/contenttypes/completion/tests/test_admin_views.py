#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_
from hamcrest import contains
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import has_key
from hamcrest import assert_that

import fudge

from datetime import datetime

from zope import interface
from zope import component

from zope.component.hooks import getSite

from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.app.contenttypes.completion import COMPLETION_PATH_NAME
from nti.app.contenttypes.completion import BUILD_COMPLETION_VIEW
from nti.app.contenttypes.completion import RESET_COMPLETION_VIEW
from nti.app.contenttypes.completion import USER_DATA_COMPLETION_VIEW
from nti.app.contenttypes.completion import COMPLETED_ITEMS_PATH_NAME
from nti.app.contenttypes.completion import AWARDED_COMPLETED_ITEMS_PATH_NAME

from nti.app.contenttypes.completion.tests import CompletionTestLayer
from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.contenttypes.completion.tests.models import PersistentCompletableItem
from nti.app.contenttypes.completion.tests.models import PersistentCompletionContext

from nti.app.products.courseware_admin import VIEW_COURSE_ROLES

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.users.utils import set_user_creation_site

from nti.contenttypes.completion.completion import CompletedItem

from nti.contenttypes.completion.interfaces import ICompletionContext
from nti.contenttypes.completion.interfaces import IAwardedCompletedItemContainer
from nti.contenttypes.completion.interfaces import IPrincipalCompletedItemContainer
from nti.contenttypes.completion.interfaces import IPrincipalAwardedCompletedItemContainer

from nti.contenttypes.completion.utils import get_indexed_completed_items

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.coremetadata.interfaces import IContained

from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.dataserver.authorization import ROLE_SITE_ADMIN
from nti.dataserver.authorization import ROLE_CONTENT_EDITOR

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users.users import User

from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid
from nti.ntiids.oids import to_external_ntiid_oid
from hamcrest.library.number.ordering_comparison import greater_than

from nti.traversal.traversal import find_interface

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

        # check index
        with mock_dataserver.mock_db_trans(self.ds):
            items = get_indexed_completed_items(user1_username)
            assert_that(items, has_length(1))

        # rebuild index
        rebuild_url = '/dataserver2/@@RebuildCompletedItemsCatalog'
        res = self.testapp.post(rebuild_url)
        assert_that(res.json_body,
                    has_entry('Items', has_length(greater_than(1))))

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
    

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    def test_user_deletion(self):
        now = datetime.utcnow()
        user1_username = 'user1_username'
        admin_username = 'sjohnson@nextthought.com'
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(user1_username)
            completion_context = PersistentCompletionContext()
            completion_context.containerId = 'container_id'
            interface.alsoProvides(completion_context, IContained)

            item1 = PersistentCompletableItem('ntiid1')
            item1.containerId = 'container_id'

            user = User.get_user(admin_username)
            for x in (completion_context, item1):
                user.addContainedObject(x)

            # Add completed item
            user1 = User.get_user(user1_username)
            user_container = component.queryMultiAdapter((user1, completion_context),
                                                         IPrincipalCompletedItemContainer)
            completed_item1 = CompletedItem(Principal=user1,
                                            Item=item1,
                                            CompletedDate=now)
            user_container.add_completed_item(completed_item1)

        with mock_dataserver.mock_db_trans(self.ds):
            items = get_indexed_completed_items(user1_username)
            assert_that(items, has_length(1))

        with mock_dataserver.mock_db_trans(self.ds):
            User.delete_entity(user1_username)
            items = get_indexed_completed_items(user1_username)
            assert_that(items, has_length(0))

class TestAdminAwardViews(ApplicationLayerTest):
    
    layer = PersistentInstructedCourseApplicationTestLayer
    
    default_origin = 'http://platform.ou.edu'
    
    course_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'
    
    @WithSharedApplicationMockDS(testapp=True, users=True)
    @fudge.patch('nti.contenttypes.completion.policies.CompletableItemAggregateCompletionPolicy.is_complete')
    def test_awarded_completed_items(self, mock_is_complete):
        
        awarded_user_username = u'rocket.raccoon'
        
        test_site_admin_username = u'I.Am.Groot'
        
        course_admin_username = u'peter.quill'
        
        course_editor_username = u'drax.destroyer'
        
        # Setup
        with mock_dataserver.mock_db_trans(self.ds):
            awarded_user = self._create_user(awarded_user_username)
            course_admin = self._create_user(course_admin_username)
            course_editor = self._create_user(course_editor_username)
            set_user_creation_site(awarded_user, 'platform.ou.edu')
            set_user_creation_site(course_admin, 'platform.ou.edu')
            set_user_creation_site(course_editor, 'platform.ou.edu')
                   
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course = entry.__parent__
            user = User.get_user(awarded_user_username)
            enrollment_manager = ICourseEnrollmentManager(course)
            enrollment_manager.enroll(user)
            
            completion_context = find_interface(entry, ICompletionContext)
            item1 = PersistentCompletableItem('ntiid1')
            item2 = PersistentCompletableItem('ntiid2')
            non_contained_item = PersistentCompletableItem('non_contained_item')
            item1.containerId = 'container_id'
            item2.containerId = 'container_id'
            interface.alsoProvides(completion_context, IContained)
            user = User.get_user(course_admin_username)
            for item in (item1, item2):
                user.addContainedObject(item)
            item_ntiid1 = to_external_ntiid_oid(item1)
            item1.ntiid = item_ntiid1
            item_ntiid2 = to_external_ntiid_oid(item2)
            item2.ntiid = item_ntiid2
            non_contained_item_ntiid = to_external_ntiid_oid(non_contained_item)
            non_contained_item.ntiid = non_contained_item_ntiid
            
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            
            principal_role_manager = IPrincipalRoleManager(getSite())
            principal_role_manager.assignRoleToPrincipal(ROLE_SITE_ADMIN.id,
                                                         test_site_admin_username)
            principal_role_manager.assignRoleToPrincipal(ROLE_CONTENT_EDITOR.id,
                                                         course_admin_username)
            
            entry = find_object_with_ntiid(self.course_ntiid)
            course_oid = to_external_ntiid_oid(ICourseInstance(entry))
        
        course_admin_environ = self._make_extra_environ(user=course_admin_username)
        course_editor_environ = self._make_extra_environ(course_editor_username)
        user_environ = self._make_extra_environ(awarded_user_username)
        nt_admin_environ = self._make_extra_environ()
        
        # Admin links
        course = self.testapp.get('/dataserver2/Objects/%s' % course_oid)
        course_ext = course.json_body
        course_roles_href = self.require_link_href_with_rel(course_ext, VIEW_COURSE_ROLES)
        
        data = dict()
        data['roles'] = roles = dict()
        roles['instructors'] = list([course_admin_username])
        roles['editors'] = list([course_editor_username])

        #Set up instructor
        self.testapp.put_json(course_roles_href, data)
        
        def get_enr():
            res = self.testapp.get('/dataserver2/users/%s/Courses/EnrolledCourses' % awarded_user_username,
                                   extra_environ=user_environ)
            res = res.json_body['Items'][0]
            return res
        
        enr_res = get_enr()
        
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            awarded_user = User.get_user(awarded_user_username)
            user_awarded_container = component.getMultiAdapter((awarded_user, completion_context),
                                                       IPrincipalAwardedCompletedItemContainer)
            course_awarded_container = IAwardedCompletedItemContainer(completion_context)
            assert_that(user_awarded_container.get_completed_item_count(), is_(0))
            assert_that(course_awarded_container.get_completed_item_count(item1), is_(0))
            
        award_completed_url = self.require_link_href_with_rel(enr_res, AWARDED_COMPLETED_ITEMS_PATH_NAME)
        data = {'MimeType': 'application/vnd.nextthought.completion.awardedcompleteditem', 'completable_ntiid': item_ntiid1}
        # Check permissions
        self.testapp.post_json(award_completed_url, data, extra_environ=user_environ, status=403)
        self.testapp.post_json(award_completed_url, data, extra_environ=course_editor_environ, status=403)
        
        res = self.testapp.post_json(award_completed_url, data, extra_environ=course_admin_environ)

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):

            assert_that(res.json_body, not has_key('Item'))
            assert_that(res.json_body, not has_key('Principal'))
            assert_that(res.json_body, has_key('awarder'))
            
            assert_that(res.json_body['reason'], is_(None))
            
            assert_that(user_awarded_container.get_completed_item_count(), is_(1))
            assert_that(user_awarded_container[item_ntiid1].awarder.username, is_(course_admin_username))
            assert_that(user_awarded_container[item_ntiid1].Principal.username, is_(awarded_user_username))
            assert_that(user_awarded_container[item_ntiid1].Item, is_(item1))
            
            assert_that(course_awarded_container.get_completed_item_count(item1), is_(1))
            assert_that(course_awarded_container.get_completed_item_count(item2), is_(0))
         
        # Should work even without MimeType explicitly passed in   
        data = {'completable_ntiid': item_ntiid2, 'reason': 'Good soup'}
        res = self.testapp.post_json(award_completed_url, data, extra_environ=course_admin_environ)
        
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            assert_that(res.json_body['reason'], is_('Good soup'))
            assert_that(user_awarded_container.get_completed_item_count(), is_(2))
            assert_that(course_awarded_container.get_completed_item_count(item1), is_(1))
            assert_that(course_awarded_container.get_completed_item_count(item2), is_(1))
            
        # POST completable that already exists; test 409 and being able to overwrite
        data['reason'] = 'Number one'    
        res = self.testapp.post_json(award_completed_url, data, extra_environ=course_admin_environ, status=409)
        
        overwrite_awarded_link = self.require_link_href_with_rel(res.json_body, 'overwrite')
        res = self.testapp.post_json(overwrite_awarded_link, data, extra_environ=course_admin_environ)
        
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            assert_that(res.json_body['reason'], is_('Number one'))
            assert_that(user_awarded_container.get_completed_item_count(), is_(2))
            assert_that(course_awarded_container.get_completed_item_count(item1), is_(1))
            assert_that(course_awarded_container.get_completed_item_count(item2), is_(1))
            
        # POST with ntiid that doesn't match an item and with item ntiid that doesn't map to completable in course; both should 422
        data = {'completable_ntiid': non_contained_item_ntiid}
        self.testapp.post_json(award_completed_url, data, extra_environ=course_admin_environ, status=422)
        
        data = {'completable_ntiid': 'not_a_valid_ntiid'}
        self.testapp.post_json(award_completed_url, data, extra_environ=course_admin_environ, status=422)
