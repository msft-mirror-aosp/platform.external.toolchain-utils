#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.

__author__ = 'kbaclawski@google.com (Krystian Baclawski)'

import collections
import os.path


class Shell(object):
  """Class used to build a string representation of a shell command."""

  def __init__(self, cmd, *args, **kwargs):
    assert all(key in ['opts', 'path'] for key in kwargs)

    self._cmd = cmd
    self._path = kwargs.get('path', '')
    self._opts = kwargs.get('opts', [])
    self._args = args

  def __str__(self):
    cmdline = [os.path.join(self._path, self._cmd)]
    cmdline.extend(self._opts)
    cmdline.extend(self._args)

    return ' '.join(cmdline)

  def AddOption(self, option):
    self._opts.append(option)


class Chain(collections.MutableSequence):
  """Container that chains shell commands using && operator."""

  def __init__(self, *commands):
    self._commands = []
    self._commands.extend(commands)

  @staticmethod
  def _ValidateType(command):
    if type(command) not in [str, Shell, Chain]:
      raise TypeError('Command cannot have %s type.' % type(command))
    else:
      return command

  def __contains__(self, command):
    return command in self._commands

  def __iter__(self):
    return iter(self._commands)

  def __len__(self):
    return len(self._commands)

  def __getitem__(self, index):
    return self._commands[index]

  def __setitem__(self, index, command):
    self._commands[index] = self._ValidateType(command)

  def __delitem__(self, index):
    del self._commands[index]

  def insert(self, index, command):
    self._commands.insert(index, self._ValidateType(command))

  def __str__(self):
    return ' && '.join(str(cmd) for cmd in self)
