#!/usr/bin/python2
"""Prototype compiler wrapper.

Only tested with: gcc, g++, clang, clang++
Installation instructions:
  1. Rename compiler from <compiler_name> to <compiler_name>.real
  2. Create symlink from this script (compiler_wrapper.py), and name it
     <compiler_name>. compiler_wrapper.py can live anywhere as long as it is
     executable.

Design doc:
https://docs.google.com/document/d/1yDgaUIa2O5w6dc3sSTe1ry-1ehKajTGJGQCbyn0fcEM
"""

from __future__ import print_function

import os
import sys

import bisect_driver

WRAPPED = '%s.real' % sys.argv[0]
BISECT_STAGE = os.environ.get('BISECT_STAGE')
DEFAULT_BISECT_DIR = os.path.expanduser('~/ANDROID_BISECT')
BISECT_DIR = os.environ.get('BISECT_DIR') or DEFAULT_BISECT_DIR


def Main(_):
  if not os.path.islink(sys.argv[0]):
    print("Compiler wrapper can't be called directly!")
    return 1

  execargs = [WRAPPED] + sys.argv[1:]

  if BISECT_STAGE not in bisect_driver.VALID_MODES:
    os.execv(WRAPPED, [WRAPPED] + sys.argv[1:])

  bisect_driver.bisect_driver(BISECT_STAGE, BISECT_DIR, execargs)


if __name__ == '__main__':
  sys.exit(Main(sys.argv[1:]))
