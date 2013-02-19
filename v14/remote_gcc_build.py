#!/usr/bin/python
#
# Copyright 2012 Google Inc. All Rights Reserved.

"""Script to use remote try-bot build image with local gcc."""

import argparse
import os
import sys

from utils import command_executer
from utils import misc

branch1 = "not_used_by_others"
branch2 = "the_actural_branch_used_in_this_script"


class GccTrybotRunner(object):
  """Remote try bot class."""

  def __init__(self, chromeos_root, new_gcc_dir, target):
    self.new_gcc_dir = new_gcc_dir
    self.target = target
    self.chromeos_root = chromeos_root
    self.ce = command_executer.GetCommandExecuter()

  def RunCommand(self, commands):
    assert not self.ce.RunCommand(commands), "{0} failed".format(commands)

  def Run(self):
    """The actual running commands."""
    gcc_path = os.path.join(self.chromeos_root, "src/third_party/gcc")
    assert os.path.isdir(gcc_path), ("{0} is not a valid chromeos root"
                                     .format(self.chromeos_root))
    assert os.path.isdir(self.new_gcc_dir), ("{0} is not a valid dir for gcc"
                                             "source".format(self.new_gcc_dir))

    os.chdir(gcc_path)

    # These commands make sure we have a fresh branch
    # "the_actural_branch_used_in_this_script"
    commands = ("git checkout -B {0} &&"
                "git branch -D {1} &&"
                "git checkout -b {1} -t cros/master &&"
                "rm -rf *".format(branch1, branch2))
    self.RunCommand(commands)

    commands = ("rsync -az --exclude='*.svn' --exclude='*.git'"
                " {0}/ .".format(self.new_gcc_dir))
    self.RunCommand(commands)

    commands = "git add -A . && git commit -m \"test\""
    self.RunCommand(commands)

    cbuildbot_path = os.path.join(self.chromeos_root, "chromite/buildbot")
    os.chdir(cbuildbot_path)
    commands = ("./cbuildbot -p \"chromiumos/third_party/gcc\" --remote"
                " {0}".format(self.target))
    self.RunCommand(commands)
    return 0


def Main(argv):
  """The main function."""
  # Common initializations
  parser = argparse.ArgumentParser()
  parser.add_argument("-c", "--chromeos_root", required=True,
                      dest="chromeos_root", help="The chromeos_root")
  parser.add_argument("-g", "--gcc_dir", required=True, dest="gcc_dir",
                      help="The gcc dir")
  parser.add_argument("-t", "--type", required=True, dest="target",
                      help=("The target to be build, the list is at"
                            " $(chromeos_root)/chromite/buildbot/cbuildbot"
                            " --list -all"))

  args = parser.parse_args(argv[1:])
  new_gcc_dir = misc.CanonicalizePath(args.gcc_dir)
  target = args.target
  chromeos_root = misc.CanonicalizePath(args.chromeos_root)
  remote_trybot = GccTrybotRunner(chromeos_root, new_gcc_dir, target)
  return remote_trybot.Run()

if __name__ == "__main__":
  retval = Main(sys.argv)
  sys.exit(retval)
