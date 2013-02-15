# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class Field(object):
  """Class representing a Field in an experiment file."""

  def __init__(self, name, value, append, type_filter):
    self.name = name
    self.value = value
    self.append = append
    self.type_filter = type_filter


class Settings(object):
  """Class representing settings (a set of fields) from an experiment file."""

  def __init__(self, name, settings_type):
    self.name = name
    self.settings_type = settings_type
    self.fields = {}
    self.used = {}
    self.parent = None

  def SetParentSettings(self, settings):
    """Set the parent settings which these settings can inherit from."""
    self.parent = settings

  def AddField(self, field):
    name = field.name
    if field.type_filter:
      name += field.type_filter

    if name in self.fields:
      raise Exception("Field %s defined previously." % name)

    self.fields[name] = field

  def GetField(self, name, type_filter=None, required=False, inherit=True):
    """Get the value of a field with a given name."""
    key = name
    if type_filter:
      key += type_filter

    if key not in self.fields:
      if self.parent and inherit:
        return self.parent.GetField(name, type_filter)
      elif required:
        raise Exception("Required field '%s' not defined in '%s' settings." %
                        (key, self.name))
      else:
        return None

    self.used[key] = True
    return self.fields[key].value

  def GetListField(self, name, type_filter=None, required=False):
    """Get the value of a field with a given name as a list."""
    text_value = self.GetField(name, type_filter, required)
    if not text_value:
      return []
    return text_value.split()

  def GetIntegerField(self, name, type_filter=None, required=False):
    """Get the value of a field with a given name as an integer."""
    text_value = self.GetField(name, type_filter, required)
    if not text_value:
      return 0
    return int(text_value)

  def Validate(self):
    """Check that all fields have been accessed."""
    for name in self.fields:
      if name not in self.used:
        raise Exception("Field %s is invalid." % name)
