#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

from utils import command_executer


class AutotestRunner(object):
  def __init__(self):
    self._ce = command_executer.GetCommandExecuter()

  def Run(self, machine_name, chromeos_root, board, autotest_name,
          autotest_args):
    command = "cd %s/src/scripts" % chromeos_root
    options = ""
    if board:
      options += " --board=%s" % board
    if autotest_args:
      options += " %s" % autotest_args
    command += ("&& cros_sdk -- ./run_remote_tests.sh --remote=%s %s %s" %
                (machine_name,
                 options,
                 autotest_name))
    return self._ce.RunCommand(command, True)


class MockAutotestRunner(object):
  def __init__(self):
    pass

  def Run(self, machine_name, chromeos_root, board, autotest_name,
          autotest_args):
    return ["", "", 0]
