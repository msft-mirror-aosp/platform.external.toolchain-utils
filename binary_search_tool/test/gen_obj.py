#!/usr/bin/python
"""Script to generate a list of object files.

0 represents a good object file.
1 represents a bad object file.
"""

import optparse
import os
import random
import sys

import common


def Main(argv):
  """Generates a list, the value of each element is 0 or 1.

  The number of 1s in the list is specified by bad_obj_num.
  The others are all 0s. The total number of 0s and 1s is specified by obj_num.

  Args:
    argv: argument from command line
  Returns:
    0 always.
  """
  parser = optparse.OptionParser()
  parser.add_option('-n',
                    '--obj_num',
                    dest='obj_num',
                    default=common.DEFAULT_OBJECT_NUMBER,
                    help=('Number of total objects.'))
  parser.add_option('-b',
                    '--bad_obj_num',
                    dest='bad_obj_num',
                    default=common.DEFAULT_BAD_OBJECT_NUMBER,
                    help=('Number of bad objects. Must be great than or equal '
                          'to zero and less than total object number.'))
  options = parser.parse_args(argv)[0]

  obj_num = int(options.obj_num)
  bad_obj_num = int(options.bad_obj_num)
  bad_to_gen = int(options.bad_obj_num)
  obj_list = []
  for i in range(obj_num):
    if (bad_to_gen > 0 and random.randint(1, obj_num) <= bad_obj_num):
      obj_list.append(1)
      bad_to_gen -= 1
    else:
      obj_list.append(0)
  while bad_to_gen > 0:
    t = random.randint(0, obj_num - 1)
    if obj_list[t] == 0:
      obj_list[t] = 1
      bad_to_gen -= 1

  if os.path.isfile(common.OBJECTS_FILE):
    os.remove(common.OBJECTS_FILE)
  if os.path.isfile(common.WORKING_SET_FILE):
    os.remove(common.WORKING_SET_FILE)

  f = open(common.OBJECTS_FILE, 'w')
  w = open(common.WORKING_SET_FILE, 'w')
  for i in obj_list:
    f.write('{0}\n'.format(i))
    w.write('{0}\n'.format(i))
  f.close()

  print 'Generated {0} object files, with {1} bad ones.'.format(
      options.obj_num, options.bad_obj_num)

  return 0


if __name__ == '__main__':
  retval = Main(sys.argv)
  sys.exit(retval)
