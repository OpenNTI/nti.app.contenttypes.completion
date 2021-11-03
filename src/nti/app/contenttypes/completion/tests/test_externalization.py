#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_
from hamcrest import none
from hamcrest import not_none
from hamcrest import assert_that

import unittest

from datetime import datetime

from nti.app.contenttypes.credit.credit import AwardedCredit

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

from nti.contenttypes.completion.completion import AwardedCompletedItem

from nti.contenttypes.completion.tests import SharedConfiguringTestLayer

from nti.contenttypes.completion.tests.test_models import MockUser
from nti.contenttypes.completion.tests.test_models import MockCompletableItem


CLASS = StandardExternalFields.CLASS
MIMETYPE = StandardExternalFields.MIMETYPE
CREATED_TIME = StandardExternalFields.CREATED_TIME
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED


class TestExternalization(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    def test_awarded_completed(self):
        
        now = datetime.utcnow()
        user1 = MockUser(u'user1')
        user2 = MockUser(u'user2')
        completable1 = MockCompletableItem('completable1')
        
        awarded_completed_item = AwardedCompletedItem(Principal=user1,
                                                      Item=completable1,
                                                      CompletedDate=now,
                                                      awarder=user2,
                                                      reason=u'Dat boi')


        ext_obj = to_external_object(awarded_completed_item)
        
        assert_that(ext_obj[CLASS], is_('AwardedCompletedItem'))
        assert_that(ext_obj[MIMETYPE],
                    is_(AwardedCompletedItem.mime_type))
        '''
        assert_that(ext_obj[CREATED_TIME], not_none())
        assert_that(ext_obj[LAST_MODIFIED], not_none())
        assert_that(ext_obj['amount'], is_(42))
        assert_that(ext_obj['title'], is_(u'Credit conference'))
        assert_that(ext_obj['description'], is_(u'desc'))
        assert_that(ext_obj['issuer'], is_(u'my issuer'))
        assert_that(ext_obj['awarded_date'], not_none())
        assert_that(ext_obj['credit_definition']['credit_type'], is_(u'Credit'))
        assert_that(ext_obj['credit_definition']['credit_units'], is_(u'Hours'))
        '''

        factory = find_factory_for(ext_obj)
        assert_that(factory, not_none())
        
        new_io = factory()
        ext_obj['Principal'] = user1
        ext_obj['Item'] = completable1
        ext_obj['awarder'] = user2
        from IPython.terminal.debugger import set_trace;set_trace()
        update_from_external_object(new_io, ext_obj, require_updater=True)
        from IPython.terminal.debugger import set_trace;set_trace()