#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for contextlib3"""

from __future__ import division
from __future__ import print_function

import contextlib
import unittest

import contextlib3


class SomeException(Exception):
  """Just an alternative to ValueError in the Exception class hierarchy."""
  pass


class TestExitStack(unittest.TestCase):
  """Tests contextlib3.ExitStack"""

  def test_exceptions_in_exit_override_exceptions_in_with(self):

    @contextlib.contextmanager
    def raise_exit():
      raised = False
      try:
        yield
      except Exception:
        raised = True
        raise ValueError
      finally:
        self.assertTrue(raised)

    # (As noted in comments in contextlib3, this behavior is consistent with
    # how python2 works. Namely, if __exit__ raises, the exception from
    # __exit__ overrides the inner exception)
    with self.assertRaises(ValueError):
      with contextlib3.ExitStack() as stack:
        stack.enter_context(raise_exit())
        raise SomeException()

  def test_raising_in_exit_doesnt_block_later_exits(self):
    exited = []

    @contextlib.contextmanager
    def raise_exit():
      try:
        yield
      finally:
        exited.append('raise')
        raise ValueError

    @contextlib.contextmanager
    def push_exit():
      try:
        yield
      finally:
        exited.append('push')

    with self.assertRaises(ValueError):
      with contextlib3.ExitStack() as stack:
        stack.enter_context(push_exit())
        stack.enter_context(raise_exit())
    self.assertEqual(exited, ['raise', 'push'])

    exited = []
    with self.assertRaises(ValueError):
      with contextlib3.ExitStack() as stack:
        stack.enter_context(push_exit())
        stack.enter_context(raise_exit())
        raise SomeException()
    self.assertEqual(exited, ['raise', 'push'])

  def test_push_doesnt_enter_the_context(self):
    exited = []

    test_self = self

    class Manager(object):
      """A simple ContextManager for testing purposes"""

      def __enter__(self):
        test_self.fail('context manager was entered :(')

      def __exit__(self, *args, **kwargs):
        exited.append(1)

    with contextlib3.ExitStack() as stack:
      stack.push(Manager())
      self.assertEqual(exited, [])
    self.assertEqual(exited, [1])

  def test_callbacks_are_run_properly(self):
    callback_was_run = []

    def callback(arg, some_kwarg=None):
      self.assertEqual(arg, 41)
      self.assertEqual(some_kwarg, 42)
      callback_was_run.append(1)

    with contextlib3.ExitStack() as stack:
      stack.callback(callback, 41, some_kwarg=42)
      self.assertEqual(callback_was_run, [])
    self.assertEqual(callback_was_run, [1])

    callback_was_run = []
    with self.assertRaises(ValueError):
      with contextlib3.ExitStack() as stack:
        stack.callback(callback, 41, some_kwarg=42)
        raise ValueError()
    self.assertEqual(callback_was_run, [1])

  def test_finallys_are_run(self):
    finally_run = []

    @contextlib.contextmanager
    def append_on_exit():
      try:
        yield
      finally:
        finally_run.append(0)

    with self.assertRaises(ValueError):
      with contextlib3.ExitStack() as stack:
        stack.enter_context(append_on_exit())
        raise ValueError()
    self.assertEqual(finally_run, [0])

  def test_unwinding_happens_in_reverse_order(self):
    exit_runs = []

    @contextlib.contextmanager
    def append_things(start_push, end_push):
      exit_runs.append(start_push)
      try:
        yield
      finally:
        exit_runs.append(end_push)

    with contextlib3.ExitStack() as stack:
      stack.enter_context(append_things(1, 4))
      stack.enter_context(append_things(2, 3))
    self.assertEqual(exit_runs, [1, 2, 3, 4])

    exit_runs = []
    with self.assertRaises(ValueError):
      with contextlib3.ExitStack() as stack:
        stack.enter_context(append_things(1, 4))
        stack.enter_context(append_things(2, 3))
        raise ValueError
    self.assertEqual(exit_runs, [1, 2, 3, 4])

  def test_exceptions_are_propagated(self):

    @contextlib.contextmanager
    def die_on_regular_exit():
      yield
      self.fail('Unreachable in theory')

    with self.assertRaises(ValueError):
      with contextlib3.ExitStack() as stack:
        stack.enter_context(die_on_regular_exit())
        raise ValueError()

  def test_exceptions_can_be_blocked(self):

    @contextlib.contextmanager
    def block():
      try:
        yield
      except Exception:
        pass

    with contextlib3.ExitStack() as stack:
      stack.enter_context(block())
      raise ValueError()

  def test_objects_are_returned_from_enter_context(self):

    @contextlib.contextmanager
    def yield_arg(arg):
      yield arg

    with contextlib3.ExitStack() as stack:
      val = stack.enter_context(yield_arg(1))
      self.assertEqual(val, 1)


if __name__ == '__main__':
  unittest.main()
