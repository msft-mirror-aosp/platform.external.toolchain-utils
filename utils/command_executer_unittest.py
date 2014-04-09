#!/usr/bin/python

"""Unittest for command_executer.py."""
import time
import unittest

import command_executer


class CommandExecuterTest(unittest.TestCase):
  def testTimeout(self):
    timeout = 1
    logging_level = "average"
    ce = command_executer.CommandExecuter(logging_level)
    start = time.time()
    command = "sleep 20"
    ce.RunCommand(command, command_timeout=timeout, terminated_timeout=timeout)
    end = time.time()
    self.assertTrue(round(end - start) == timeout)

if __name__ == "__main__":
  unittest.main()
