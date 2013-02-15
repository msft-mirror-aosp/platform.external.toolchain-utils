#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to build the ChromeOS toolchain.

This script sets up the toolchain if you give it the gcctools directory.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import getpass
import optparse
import re
import socket
import sys
import tempfile
from utils import utils

# Common initializations
(rootdir, basename) = utils.GetRoot(sys.argv[0])
utils.InitLogger(rootdir, basename)


def CreateP4Client(client_name, p4_port, p4_paths, checkoutdir):
  """Creates a perforce client from the given parameters."""
  command = "cd " + checkoutdir
  command += "; cp ${HOME}/.p4config ."
  command += "; echo \"P4PORT=" + p4_port + "\" >> .p4config"
  command += "; echo \"P4CLIENT=" + client_name + "\" >> .p4config"
  command += "; g4 client -a " + " -a ".join(p4_paths)
  print command
  retval = utils.RunCommand(command)
  return retval


def DeleteP4Client(client_name):
  command = "g4 client -d " + client_name
  retval = utils.RunCommand(command)
  return retval


def SyncP4Client(client_name, checkoutdir, revision=None):
  command = "cd " + checkoutdir
  command += "; g4 sync ..."
  retval = utils.RunCommand(command)
  return retval


def GetP4PathsForTool(client_name, tool, branch_path):
  p4_paths = []
  if branch_path[-1] == "/":
    branch_path = branch_path[0:-1]
  if tool == "gcc":
    p4_paths.append("\"" + branch_path + "/google_vendor_src_branch/" +
                    "gcc/gcc-4.4.3/..." +
                    " //" + client_name + "/gcc/gcc-4.4.3/..." +
                    "\"")
  return p4_paths


def GetGitRepoForTool(tool):
  # This should return the correct server repository when the script
  # is fully done.
  if tool == "gcc":
    return "~/a/gittest/gccgit2"


def CreateGitClient(git_repo, checkoutdir):
  command = "cd " + checkoutdir
  command += " && git clone " + git_repo + " ."
  command += " && rm -rf *"
  retval = utils.RunCommand(command)
  return retval


def GetLatestCL(client_name, checkoutdir):
  command = "cd " + checkoutdir
  command += " && g4 changes -m1"
  (status, stdout, stderr) = utils.RunCommand(command, True)
  if status != 0:
    return -1
  mo = re.match("^Change (\d+)", stdout)
  if mo is None:
    return -1
  return mo.groups(0)[0]


def WriteStringToFile(filename, string):
  f = open(filename, "w")
  f.write(string)
  f.close()


def PushToRemoteGitRepo(checkoutdir, branch, message_file):
  command = "cd " + checkoutdir
###  command += " && git add . "
  # For testing purposes, I am only adding a single file to the
  # remote repository.
  command += " && git add gcc/gcc-4.4.3/COPYING.LIB"
  command += " && git commit -F " + message_file
  command += " && git push origin " + branch + ":" + branch
  retval = utils.RunCommand(command)
  return retval


def Main():
  """The main function."""
  parser = optparse.OptionParser()
  parser.add_option("-t", "--tool", dest="tool",
                    help="Tool can be gcc or binutils.")
  parser.add_option("-b", "--branch", dest="branch",
                    help="Full branch path to use, if not the trunk.")

  options = parser.parse_args()[0]

  if options.tool is None:
    parser.print_help()
    sys.exit()

  if not options.branch:
    branch_path = ("//depot2/gcctools/")
  else:
    branch_path = ("//depot2/branches/" + options.branch +
                   "/gcctools")

  # Setup a perforce checkout of Crosstool trunk or branch.
  temp_dir = tempfile.mkdtemp()
  client_name = getpass.getuser() + "-" + socket.gethostname() + "-" + temp_dir
  client_name = str.replace(client_name, "/", "-")
  p4_paths = GetP4PathsForTool(client_name, options.tool, branch_path)
  git_repo = GetGitRepoForTool(options.tool)
  status = CreateGitClient(git_repo, temp_dir)
  utils.AssertTrue(status == 0, "Git repo cloning failed")
  status = CreateP4Client(client_name, "perforce2:2666", p4_paths, temp_dir)
  utils.AssertTrue(status == 0, "Could not create p4 client")
  status = SyncP4Client(client_name, temp_dir)
  utils.AssertTrue(status == 0, "Could not sync p4 client")
  changelist = GetLatestCL(client_name, temp_dir)
  message_file = tempfile.mktemp()
  WriteStringToFile(message_file, "Sync'd to revision " + changelist)
  status = PushToRemoteGitRepo(temp_dir, "master", message_file)
  utils.AssertTrue(status == 0, "Could not push to remote repo")
  status = DeleteP4Client(client_name)
  utils.AssertTrue(status == 0, "Could not delete p4 client")


if __name__ == "__main__":
  Main()


