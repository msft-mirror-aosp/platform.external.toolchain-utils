#!/usr/bin/python2
#
# Copyright 2015 Google Inc. All Rights Reserved.
#
# This script takes a single argument, the name of a file (normally expected to
# be 'build_image'), which should be a shell script.  It then creates a new
# output file, named <input_file>.edited, and it copies each line from the
# input file to the output file.  If the line from the input file contains the
# string 'eclean', it prepends a '#' to the line before copying it to the
# output file, in effect commenting out any lines that contain 'eclean'.
#

import sys
import os


def Main(args):

  if args:
    filename = args[0]
    if not os.path.exists(filename):
      return 1
  else:
    return 1

  outname = filename + '.edited'
  with open(filename, 'r') as input_file:
    lines = input_file.readlines()
    with open(outname, 'w') as out_file:
      for line in lines:
        if line.find('eclean') >= 0:
          out_line = '# ' + line
        else:
          out_line = line
        out_file.write(out_line)

  return 0


if __name__ == '__main__':
  retval = Main(sys.argv[1:])
  sys.exit(retval)
