#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""lock_machine.py related unit-tests.

MachineManagerTest tests MachineManager.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"


import os
import tempfile
import unittest
from utils import command_executer
from utils import utils


class DivideAndMergeProfilesTest(unittest.TestCase):
  def setUp(self):
    self._ce = command_executer.GetCommandExecuter()
    self._program_dir = tempfile.mkdtemp()
    print self._program_dir
    self._writeProgram()
    self._writeMakefile()
    with utils.WorkingDirectory(self._program_dir):
      self._ce.RunCommand("make")
    num_profile_dirs = 2
    self._profile_dirs = []
    for i in range(num_profile_dirs):
      profile_dir = tempfile.mkdtemp()
      command = ("GCOV_PREFIX_STRIP=%s GCOV_PREFIX=$(/bin/pwd) "
                 " %s/program" %
                 (profile_dir.count("/"),
                  self._program_dir))
      with utils.WorkingDirectory(profile_dir):
        self._ce.RunCommand(command)
      self._profile_dirs.append(profile_dir)
    self._merge_program = "/home/build/static/projects/crosstool/profile-merge/v14.5/profile_merge.par"

  def _writeMakefile(self):
    makefile_contents = """
CC = gcc

CFLAGS = -fprofile-generate

SRCS=$(wildcard *.c)

OBJS=$(SRCS:.c=.o)

all: program

program: $(OBJS)
	$(CC) -o $@ $^ $(CFLAGS)

%.o: %.c
	$(CC) -c -o $@ $^ $(CFLAGS)"""
    makefile = os.path.join(self._program_dir, "Makefile")
    with open(makefile, "w") as f:
      print >> f, makefile_contents

  def _writeProgram(self, num_files=100):
    for i in range(num_files):
      current_file = os.path.join(self._program_dir, "%s.c" % i)
      with open(current_file, "w") as f:
        if i != num_files - 1:
          print >> f, "extern void foo%s();" % (i + 1)
          print >> f, "void foo%s(){foo%s();}" % (i, i + 1)
        else:
          print >> f, "void foo%s(){printf(\"\");}" % i
        if i == 0:
          print >> f, "int main(){foo%s(); return 0;}" % i

  def testMerge(self):
    # First do a regular merge.
    reference_output = tempfile.mkdtemp()
    command = ("%s --inputs=%s --output=%s" %
               (self._merge_program,
                ",".join(self._profile_dirs),
                reference_output))
    self._ce.RunCommand(command)

    my_output = tempfile.mkdtemp()
    my_merge_program = os.path.join(os.path.dirname(__file__),
                                    "divide_and_merge_profiles.py")
    command = ("python %s --inputs=%s --output=%s "
               "--chunk_size=10 "
               "--merge_program=%s" %
               (my_merge_program,
                ",".join(self._profile_dirs),
                my_output,
                self._merge_program))
    self._ce.RunCommand(command)

    command = "diff -uNr %s %s" % (reference_output, my_output)
    ret = self._ce.RunCommand(command)
    self.assertTrue(ret == 0)

if __name__ == "__main__":
  unittest.main()
