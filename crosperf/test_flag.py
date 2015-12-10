# Copyright 2011 Google Inc. All Rights Reserved.

"""A global variable for testing."""


_is_test = [False]


def SetTestMode(flag):
  _is_test[0] = flag


def GetTestMode():
  return  _is_test[0]
