#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.


class Settings(object):
  """Class representing settings (a set of fields) from an experiment file."""

  def __init__(self, name, settings_type):
    self.name = name
    self.settings_type = settings_type
    self.fields = {}
    self.parent = None

  def SetParentSettings(self, settings):
    """Set the parent settings which these settings can inherit from."""
    self.parent = settings

  def AddField(self, field):
    name = field.name
    if name in self.fields:
      raise Exception("Field %s defined previously." % name)
    self.fields[name] = field

  def SetField(self, name, value, append=False):
    if name not in self.fields:
      raise Exception("'%s' is not a valid field in '%s' settings"
                      % (name, self.settings_type))
    if append:
      self.fields[name].Append(value)
    else:
      self.fields[name].Set(value)

  def GetField(self, name):
    """Get the value of a field with a given name."""
    if name not in self.fields:
      raise Exception("Field '%s' not a valid field in '%s' settings." %
                      (name, self.name))
    field = self.fields[name]
    if not field.assigned and field.required:
      raise Exception("Required field '%s' not defined in '%s' settings." %
                      (name, self.name))

    return self.fields[name].Get()

  def Inherit(self):
    """Inherit any unset values from the parent settings."""
    for name in self.fields:
      if (not self.fields[name].assigned and self.fields[name].inheritable
          and self.parent):
        self.fields[name].Set(self.parent.GetField(name))

  def Override(self, settings):
    """Override settings with settings from a different object."""
    for name in settings.fields:
      if name in self.fields and settings.fields[name].assigned:
        self.fields[name].Set(settings.GetField(name))

  def Validate(self):
    """Check that all required fields have been set."""
    for name in self.fields:
      if not self.fields[name].assigned and self.fields[name].required:
        raise Exception("Field %s is invalid." % name)
