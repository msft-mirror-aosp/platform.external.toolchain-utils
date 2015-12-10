#!/usr/bin/python
"""Prints out index for every object file, starting from 0."""

import sys

from utils import command_executer
import common


def Main():
  ce = command_executer.GetCommandExecuter()
  _, l, _ = ce.RunCommandWOutput(
      'cat {0} | wc -l'.format(common.OBJECTS_FILE), print_to_console=False)
  for i in range(0, int(l)):
    print i


if __name__ == '__main__':
  Main()
  sys.exit(0)
