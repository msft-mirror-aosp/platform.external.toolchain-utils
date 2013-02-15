#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.


class Field(object):
  """Class representing a Field in an experiment file."""

  def __init__(self, name, required, default, inheritable, description):
    self.name = name
    self.required = required
    self.assigned = False
    self.default = default
    self._value = default
    self.inheritable = inheritable
    self.description = description

  def Set(self, value):
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
  def __init__(self, name, required=False, default="", inheritable=False,
               description=""):
    super(TextField, self).__init__(name, required, default, inheritable,
                                    description)

  def _Parse(self, value):
    return str(value)


class BooleanField(Field):
  def __init__(self, name, required=False, default=False, inheritable=False,
               description=""):
    super(BooleanField, self).__init__(name, required, default, inheritable,
                                       description)

  def _Parse(self, value):
    return bool(value)


class IntegerField(Field):
  def __init__(self, name, required=False, default=0, inheritable=False,
               description=""):
    super(IntegerField, self).__init__(name, required, default, inheritable,
                                       description)

  def _Parse(self, value):
    return int(value)


class FloatField(Field):
  def __init__(self, name, required=False, default=0, inheritable=False,
               description=""):
    super(FloatField, self).__init__(name, required, default, inheritable,
                                     description)

  def _Parse(self, value):
    return float(value)


class ListField(Field):
  def __init__(self, name, required=False, default=[], inheritable=False,
               description=""):
    super(ListField, self).__init__(name, required, default, inheritable,
                                    description)

  def _Parse(self, value):
    return value.split()
