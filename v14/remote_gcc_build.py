#!/usr/bin/python
#
# Copyright 2012 Google Inc. All Rights Reserved.

"""Script to use remote try-bot build image with local gcc."""

import argparse
import glob
import os
import re
import socket
import sys
import time

from utils import command_executer
from utils import logger
from utils import misc

branch1 = "not_used_by_others"
branch2 = "the_actual_branch_used_in_this_script"
current_branch = "release-R25-3428.B"
current_version = "*30474"
actual_version = "R26-3473.0.0"
sleep_time = 600


def GetPatchNum(output):
  lines = output.splitlines()
  line = [l for l in lines if "DRAFT" in l][0]
  patch_num = re.findall(r"\d+", line)[0]
  if "gerrit-int" in line:
    patch_num = "*" + patch_num
  return patch_num


def FindResultIndex(reason, time_out=10800):
  """Find the build id of the build at trybot server."""
  running_time = 0
  while running_time < time_out:
    num = GetBuildNumber(reason)
    if num:
      return num
    logger.GetLogger().LogOutput("{0} minutes passed."
                                 .format(running_time / 60))
    logger.GetLogger().LogOutput("Sleeping {0} seconds.".format(sleep_time))
    time.sleep(sleep_time)
    running_time += sleep_time
  logger.GetLogger().LogWarning("No results after {0} seconds, time out"
                                .format(time_out))
  return 0


def GetBuildNumber(reason):
  """Get the build num from build log."""
  file_dir = os.path.dirname(os.path.realpath(__file__))
  commands = ("{0}/utils/buildbot_json.py builds "
              "http://chromegw/p/tryserver.chromiumos/"
              .format(file_dir))
  ce = command_executer.GetCommandExecuter()
  _, buildinfo, _ = ce.RunCommand(commands, return_output=True,
                                  print_to_console=False)

  my_info = buildinfo.splitlines()
  current_line = 1
  while current_line < len(my_info):
    my_dict = {}
    while True:
      key = my_info[current_line].split(":")[0].strip()
      value = my_info[current_line].split(":", 1)[1].strip()
      my_dict[key] = value
      current_line += 1
      if "Build" in key or current_line == len(my_info):
        break
    change_lists = my_dict["reason"].split()[-1]
    if reason:
      change_list_hit = str(reason) in change_lists
    else:
      change_list_hit = (current_version in change_lists and
                         "," not in change_lists)
    if ("True" not in my_dict["completed"] or
        not change_list_hit):
      continue
    number = int(my_dict["number"])
    return number
  return 0


def DownloadImage(target, index, dest):
  """Download files of this run to dest."""
  if not os.path.exists(dest):
    os.makedirs(dest)

  ls_cmd = ("gsutil ls gs://chromeos-image-archive/trybot-{0}/{1}-b{2}"
            .format(target, actual_version, index))

  download_cmd = ("$(which gsutil) cp {0} {1}".format("{0}", dest))
  ce = command_executer.GetCommandExecuter()

  _, out, _ = ce.RunCommand(ls_cmd, return_output=True, print_to_console=True)
  lines = out.splitlines()
  download_files = ["autotest.tar", "chromeos-chrome",
                    "chromiumos_test_image", "debug.tgz",
                    "sysroot_chromeos-base_chromeos-chrome.tar.xz"
                   ]
  for line in lines:
    if any([e in line for e in download_files]):
      cmd = download_cmd.format(line)
      if ce.RunCommand(cmd):
        logger.GetLogger().LogFatal("Command {0} failed, existing..."
                                    .format(cmd))


def UnpackImage(dest):
  """Unpack the image, the chroot build dir."""
  chrome_tbz2 = glob.glob(dest+"/*.tbz2")[0]
  commands = ("tar xJf {0}/sysroot_chromeos-base_chromeos-chrome.tar.xz "
              "-C {0} &&"
              "tar xjf {1} -C {0} &&"
              "tar xzf {0}/debug.tgz  -C {0}/usr/lib/ &&"
              "tar xf {0}/autotest.tar -C {0}/usr/local/ &&"
              "tar xJf {0}/chromiumos_test_image.tar.xz -C {0}"
              .format(dest, chrome_tbz2))
  ce = command_executer.GetCommandExecuter()
  return ce.RunCommand(commands)


class GccTrybotRunner(object):
  """Remote try bot class."""

  def __init__(self, chromeos_root, new_gcc_dir, target, local,
               dest_dir, master, chrome_version):
    self.new_gcc_dir = new_gcc_dir
    self.target = target
    self.chromeos_root = misc.CanonicalizePath(chromeos_root)
    self.local = local
    self.master = master
    self.chrome_version = chrome_version

    if self.local and dest_dir:
      self.dest_dir = misc.CanonicalizePath(dest_dir)
    elif self.local:
      raise Exception("dest_dir is needed when --local is specified")
    self.ce = command_executer.GetCommandExecuter()

  def RunCommand(self, commands):
    assert not self.ce.RunCommand(commands), "{0} failed".format(commands)

  def GetCLNumber(self):
    """Upload local gcc to gerrit and get the CL number."""
    gcc_path = os.path.join(self.chromeos_root, "src/third_party/gcc")
    assert os.path.isdir(gcc_path), ("{0} is not a valid chromeos root"
                                     .format(self.chromeos_root))

    assert os.path.isdir(self.new_gcc_dir), ("{0} is not a valid dir for gcc"
                                             "source".format(self.new_gcc_dir))

    os.chdir(gcc_path)

    # These commands make sure we have a fresh branch
    # "the_actural_branch_used_in_this_script"
    if self.master:
      commands = ("git checkout -B {0} &&"
                  "git branch -D {1} &&"
                  "git checkout -b {1} -t remotes/cros/master &&"
                  "git branch -D {0} &&"
                  "rm -rf *".format(branch1, branch2))
    else:
      commands = ("git checkout -B {0} &&"
                  "git checkout -B {1} &&"
                  "git checkout {0} &&"
                  "git branch -D {1} &&"
                  "git checkout -b {1} -t remotes/cros/{2} &&"
                  "git branch -D {0} &&"
                  "rm -rf *".format(branch1, branch2, current_branch))
    self.RunCommand(commands)

    commands = ("rsync -az --exclude='*.svn' --exclude='*.git'"
                " {0}/ .".format(self.new_gcc_dir))
    self.RunCommand(commands)
    return self.UploadPatch()

  def UploadPatch(self):
    commands = ("git add -A . &&"
                "git commit -m 'test' -m 'BUG=None' -m 'TEST=None' "
                "--amend -m 'hostname={0}' -m 'gcc_patch={1}'"
                .format(socket.gethostname(), self.new_gcc_dir))
    self.RunCommand(commands)

    commands = ("yes | repo upload . -d --cbr --no-verify")
    _, _, err = self.ce.RunCommand(commands, return_output=True)
    return GetPatchNum(err)

  def Run(self):
    """The actual running commands."""

    if self.new_gcc_dir:
      self.new_gcc_dir = misc.CanonicalizePath(self.new_gcc_dir)
      patch = self.GetCLNumber()
    else:
      patch = 0
    if self.local:
      remote_flag = "--local -r {0}".format(self.dest_dir)
    else:
      remote_flag = "--remote"
    cbuildbot_path = os.path.join(self.chromeos_root, "chromite/buildbot")
    os.chdir(cbuildbot_path)
    if patch:
      commands = ("./cbuildbot -g {0} {1} {2}"
                  .format(patch, remote_flag, self.target))
    else:
      commands = ("./cbuildbot {0} {1}"
                  .format(remote_flag, self.target))

    if self.chrome_version:
      commands += " --chrome_version={0}".format(self.chrome_version)

    description = "{0}_{1}".format(patch, self.target)
    if not self.master:
      commands += " -b {0} -g {1}".format(current_branch, current_version)
      description +="_{0}".format(current_version)
    commands += " --remote-description={0}".format(description)
    self.RunCommand(commands)
    return description


def Main(argv):
  """The main function."""
  # Common initializations
  parser = argparse.ArgumentParser()
  parser.add_argument("-c", "--chromeos_root", required=True,
                      dest="chromeos_root", help="The chromeos_root")
  parser.add_argument("-g", "--gcc_dir", default="", dest="gcc_dir",
                      help="The gcc dir")
  parser.add_argument("-t", "--type", required=True, dest="target",
                      help=("The target to be build, the list is at"
                            " $(chromeos_root)/chromite/buildbot/cbuildbot"
                            " --list -all"))
  parser.add_argument("-l", "--local", action="store_true")
  parser.add_argument("-d", "--dest_dir", dest="dest_dir",
                      help=("The dir to build the whole chromeos if"
                            " --local is set"))
  parser.add_argument("-m", "--master", action="store_true")
  parser.add_argument("--chrome_version", dest="chrome_version",
                      default="", help="The chrome version to use. "
                      "Default it will use the latest one.")

  script_dir = os.path.dirname(os.path.realpath(__file__))

  args = parser.parse_args(argv[1:])
  target = args.target
  index = 0
  description = "0_{0}".format(target)
  if not args.master:
    description +="_{0}".format(current_version)
  if not args.gcc_dir:
    index = GetBuildNumber(description)
  if not index:
    remote_trybot = GccTrybotRunner(args.chromeos_root, args.gcc_dir, target,
                                    args.local, args.dest_dir, args.master,
                                    args.chrome_version)
    description = remote_trybot.Run()
  if args.local or not args.dest_dir:
    return 0
  os.chdir(script_dir)
  dest_dir = misc.CanonicalizePath(args.dest_dir)
  index = FindResultIndex(description)
  if not index:
    logger.GetLogger().LogFatal("Remote trybot timeout")
  DownloadImage(target, index, dest_dir)
  return UnpackImage(dest_dir)

if __name__ == "__main__":
  retval = Main(sys.argv)
  sys.exit(retval)
