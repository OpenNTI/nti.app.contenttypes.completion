#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.container.contained import Contained

from zope.traversing.interfaces import IPathAdapter

from nti.app.contenttypes.completion import MessageFactory

from nti.app.contenttypes.completion import COMPLETION_POLICY_VIEW_NAME

