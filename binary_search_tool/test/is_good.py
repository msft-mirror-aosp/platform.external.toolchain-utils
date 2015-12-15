#!/usr/bin/python
"""Check to see if the working set produces a good executable."""

import sys

import common


def Main():
  working_set = common.ReadWorkingSet()
  for w in working_set:
    if w == 1:
      return 1  ## False, linking failure
  return 0


if __name__ == '__main__':
  retval = Main()
  sys.exit(retval)
