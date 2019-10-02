# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Random utilties from Python3's contextlib."""

from __future__ import division
from __future__ import print_function

import sys


class ExitStack(object):
  """https://docs.python.org/3/library/contextlib.html#contextlib.ExitStack"""

  def __init__(self):
    self._stack = []
    self._is_entered = False

  def _assert_is_entered(self):
    # Strictly, entering has no effect on the operations that call this.
    # However, if you're trying to e.g. push things to an ExitStack that hasn't
    # yet been entered, that's likely a bug.
    assert self._is_entered, 'ExitStack op performed before entering'

  def __enter__(self):
    self._is_entered = True
    return self

  def _perform_exit(self, exc_type, exc, exc_traceback):
    # I suppose a better name for this is
    # `take_exception_handling_into_our_own_hands`, but that's harder to type.
    exception_handled = False
    while self._stack:
      fn = self._stack.pop()
      # The except clause below is meant to run as-if it's a `finally` block,
      # but `finally` blocks don't have easy access to exceptions currently in
      # flight. Hence, we do need to catch things like KeyboardInterrupt,
      # SystemExit, ...
      # pylint: disable=bare-except
      try:
        # If an __exit__ handler returns a truthy value, we should assume that
        # it handled the exception appropriately. Otherwise, we need to keep it
        # with us. (PEP 343)
        if fn(exc_type, exc, exc_traceback):
          exc_type, exc, exc_traceback = None, None, None
          exception_handled = True
      except:
        # Python2 doesn't appear to have the notion of 'exception causes',
        # which is super unfortunate. In the case:
        #
        # @contextlib.contextmanager
        # def foo()
        #   try:
        #     yield
        #   finally:
        #     raise ValueError
        #
        # with foo():
        #   assert False
        #
        # ...Python will only note the ValueError; nothing about the failing
        # assertion is printed.
        #
        # I guess on the bright side, that means we don't have to fiddle with
        # __cause__s/etc.
        exc_type, exc, exc_traceback = sys.exc_info()
        exception_handled = True

    if not exception_handled:
      return False

    # Something changed. We either need to raise for ourselves, or note that
    # the exception has been suppressed.
    if exc_type is not None:
      raise exc_type, exc, exc_traceback

    # Otherwise, the exception was suppressed. Go us!
    return True

  def __exit__(self, exc_type, exc, exc_traceback):
    return self._perform_exit(exc_type, exc, exc_traceback)

  def close(self):
    """Unwinds the exit stack, unregistering all events"""
    self._perform_exit(None, None, None)

  def enter_context(self, cm):
    """Enters the given context manager, and registers it to be exited."""
    self._assert_is_entered()

    # The spec specifically notes that we should take __exit__ prior to calling
    # __enter__.
    exit_cleanup = cm.__exit__
    result = cm.__enter__()
    self._stack.append(exit_cleanup)
    return result

  # pylint complains about `exit` being redefined. `exit` is the documented
  # name of this param, and renaming it would break portability if someone
  # decided to `push(exit=foo)`, so just ignore the lint.
  # pylint: disable=redefined-builtin
  def push(self, exit):
    """Like `enter_context`, but won't enter the value given."""
    self._assert_is_entered()
    self._stack.append(exit.__exit__)

  def callback(self, callback, *args, **kwargs):
    """Performs the given callback on exit"""
    self._assert_is_entered()

    def fn(_exc_type, _exc, _exc_traceback):
      callback(*args, **kwargs)

    self._stack.append(fn)
