# Copyright 2011 Google Inc. All Rights Reserved.

"""A configure file."""
config = {}


def GetConfig(key):
  try:
    return config[key]
  except KeyError:
    return None


def AddConfig(key, value):
  config[key] = value
