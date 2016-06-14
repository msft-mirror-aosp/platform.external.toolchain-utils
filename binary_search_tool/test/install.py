#!/usr/bin/python2
"""Emulate installation of files, is_good.py should fail without this."""

from __future__ import print_function

import sys


def Main():
  # create ./installed
  with open('./installed', 'w'):
    pass

  return 0


if __name__ == '__main__':
  retval = Main()
  sys.exit(retval)
