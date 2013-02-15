#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.


class Field(object):
  """Class representing a Field in an experiment file."""

  def __init__(self, name, required, default, overridable):
    self.name = name
    self.required = required
    self.assigned = False
    self._value = default
    self.overridable = overridable

  def Set(self, value):
    if self.assigned:
      raise Exception("Field already assigned value: '%s'" % str(self._value))
    self._value = self._Parse(value)
    self.assigned = True

  def Append(self, value):
    self._value += self._Parse(value)
    self.assigned = True

  def _Parse(self, value):
    return value

  def Get(self):
    return self._value


class TextField(Field):
  def __init__(self, name, required=False, default="", overridable=False):
    super(TextField, self).__init__(name, required, default, overridable)

  def _Parse(self, value):
    return str(value)


class BooleanField(Field):
  def __init__(self, name, required=False, default=False, overridable=False):
    super(BooleanField, self).__init__(name, required, default, overridable)

  def _Parse(self, value):
    return bool(value)


class IntegerField(Field):
  def __init__(self, name, required=False, default=0, overridable=False):
    super(IntegerField, self).__init__(name, required, default, overridable)

  def _Parse(self, value):
    return int(value)


class ListField(Field):
  def __init__(self, name, required=False, default=[], overridable=False):
    super(ListField, self).__init__(name, required, default, overridable)

  def _Parse(self, value):
    return value.split()
