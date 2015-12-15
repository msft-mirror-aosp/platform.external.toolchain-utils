#!/usr/bin/python
#
# Copyright 2010 Google Inc. All Rights Reserved.

__author__ = 'asharif@google.com (Ahmad Sharif)'

import optparse
import os
import re
import sys

from utils import command_executer


def Usage(parser, message):
  print 'ERROR: ' + message
  parser.print_help()
  sys.exit(0)


def Main(argv):
  parser = optparse.OptionParser()
  options = parser.parse_args(argv)[0]

  command = 'sleep 1000'
  ce = command_executer.GetCommandExecuter()
  ce.RunCommand(command, command_timeout=1)
  return 0


if __name__ == '__main__':
  Main(sys.argv)
