#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import zope.i18nmessageid
MessageFactory = zope.i18nmessageid.MessageFactory(__name__)

COMPLETION_POLICY_VIEW_NAME = u'CompletionPolicy'
COMPLETION_DEFAULT_VIEW_NAME = u'Default'
COMPLETION_REQUIRED_VIEW_NAME = u'Required'
COMPLETION_NOT_REQUIRED_VIEW_NAME = u'NotRequired'

COMPLETION_PATH_NAME = u'Completion'
DEFAULT_REQUIRED_POLICY_PATH_NAME = u'DefaultRequiredPolicy'
COMPLETABLE_ITEMS_PATH_NAME = u'CompletableItems'
PROGRESS_PATH_NAME = u'Progress'
COMPLETED_ITEMS_PATH_NAME = u'CompletedItems'

RESET_COMPLETION_VIEW = u'ResetCompletion'
BUILD_COMPLETION_VIEW = u'BuildCompletion'
USER_DATA_COMPLETION_VIEW = u'UserCompletionData'

AWARDED_COMPLETED_ITEMS_PATH_NAME = u'AwardedCompletedItems'
DELETE_AWARDED_COMPLETED_ITEM_VIEW = u'DeleteAwardedCompletedItem'
