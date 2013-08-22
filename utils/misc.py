#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for toolchain build."""

__author__ = "asharif@google.com (Ahmad Sharif)"

from contextlib import contextmanager
import os
import re
import shutil
import sys
import time

import lock_machine

import command_executer
import logger


def GetChromeOSVersionFromLSBVersion(lsb_version):
  """Get Chromeos version from Lsb version."""
  ce = command_executer.GetCommandExecuter()
  command = "git ls-remote http://git.chromium.org/chromiumos/manifest.git"
  ret, out, _ = ce.RunCommand(command, return_output=True,
                              print_to_console=False)
  assert ret == 0, "Command %s failed" % command
  lower = []
  for line in out.splitlines():
    mo = re.search(r"refs/heads/release-R(\d+)-(\d+)\.B", line)
    if mo:
      revision = int(mo.group(1))
      build = int(mo.group(2))
      lsb_build = int(lsb_version.split(".")[0])
      if lsb_build > build:
        lower.append(revision)
  lower = sorted(lower)
  if lower:
    return "R%d-%s" % (lower[-1] + 1, lsb_version)
  else:
    return "Unknown"


def ApplySubs(string, *substitutions):
  for pattern, replacement in substitutions:
    string = re.sub(pattern, replacement, string)
  return string


def UnitToNumber(unit_num, base=1000):
  """Convert a number with unit to float."""
  unit_dict = {"kilo": base,
               "mega": base**2,
               "giga": base**3}
  unit_num = unit_num.lower()
  mo = re.search(r"(\d*)(.+)?", unit_num)
  number = mo.group(1)
  unit = mo.group(2)
  if not unit:
    return float(number)
  for k, v in unit_dict.items():
    if k.startswith(unit):
      return float(number) * v
  raise Exception("Unit: %s not found in byte: %s!" %
                  (unit,
                   unit_num))


def GetFilenameFromString(string):
  return ApplySubs(string,
                   (r"/", "__"),
                   (r"\s", "_"),
                   (r"[\^\$=\"\\\?]", ""),
                  )


def GetRoot(scr_name):
  """Break up pathname into (dir+name)."""
  abs_path = os.path.abspath(scr_name)
  return (os.path.dirname(abs_path), os.path.basename(abs_path))


def GetChromeOSKeyFile(chromeos_root):
  return os.path.join(chromeos_root,
                      "src",
                      "scripts",
                      "mod_for_test_scripts",
                      "ssh_keys",
                      "testing_rsa")


def GetChrootPath(chromeos_root):
  return os.path.join(chromeos_root,
                      "chroot")


def GetInsideChrootPath(chromeos_root, file_path):
  if not file_path.startswith(GetChrootPath(chromeos_root)):
    raise Exception("File: %s doesn't seem to be in the chroot: %s" %
                    (file_path,
                     chromeos_root))
  return file_path[len(GetChrootPath(chromeos_root)):]


def GetOutsideChrootPath(chromeos_root, file_path):
  return os.path.join(GetChrootPath(chromeos_root),
                      file_path.lstrip("/"))


def FormatQuotedCommand(command):
  return ApplySubs(command,
                   ("\"", "\\\""))


def FormatCommands(commands):
  return ApplySubs(str(commands),
                   ("&&", "&&\n"),
                   (";", ";\n"),
                   (r"\n+\s*", "\n"))


def GetImageDir(chromeos_root, board):
  return os.path.join(chromeos_root,
                      "src",
                      "build",
                      "images",
                      board)


def LabelLatestImage(chromeos_root, board, label):
  image_dir = GetImageDir(chromeos_root, board)
  latest_image_dir = os.path.join(image_dir, "latest")
  latest_image_dir = os.path.realpath(latest_image_dir)
  latest_image_dir = os.path.basename(latest_image_dir)
  with WorkingDirectory(image_dir):
    command = "ln -sf -T %s %s" % (latest_image_dir, label)
    ce = command_executer.GetCommandExecuter()
    return ce.RunCommand(command)


def DoesLabelExist(chromeos_root, board, label):
  image_label = os.path.join(GetImageDir(chromeos_root, board),
                             label)
  return os.path.exists(image_label)


def GetBuildPackagesCommand(board, usepkg=False, debug=False):
  if usepkg:
    usepkg_flag = "--usepkg"
  else:
    usepkg_flag = "--nousepkg"
  if debug:
    withdebug_flag = '--withdebug'
  else:
    withdebug_flag = '--nowithdebug'
  return ("./build_packages %s --withdev --withtest --withautotest "
          "--skip_toolchain_update %s --board=%s "
          "--accept_licenses=@CHROMEOS" %
          (usepkg_flag, withdebug_flag, board))


def GetBuildImageCommand(board, dev=False):
  dev_args = ""
  if dev:
    dev_args = "--noenable_rootfs_verification --disk_layout=2gb-rootfs"
  return "./build_image --board=%s %s test" % (board, dev_args)

def GetSetupBoardCommand(board, gcc_version=None, binutils_version=None,
                         usepkg=None, force=None):
  """Get setup_board command."""
  options = []

  if gcc_version:
    options.append("--gcc_version=%s" % gcc_version)

  if binutils_version:
    options.append("--binutils_version=%s" % binutils_version)

  if usepkg:
    options.append("--usepkg")
  else:
    options.append("--nousepkg")

  if force:
    options.append("--force")

  options.append("--accept_licenses=@CHROMEOS")

  return "./setup_board --board=%s %s" % (board, " ".join(options))


def CanonicalizePath(path):
  path = os.path.expanduser(path)
  path = os.path.realpath(path)
  return path


def GetCtargetFromBoard(board, chromeos_root):
  """Get Ctarget from board."""
  base_board = board.split("_")[0]
  command = ("source "
             "../platform/dev/toolchain_utils.sh; get_ctarget_from_board %s" %
             base_board)
  ce = command_executer.GetCommandExecuter()
  ret, out, _ = ce.ChrootRunCommand(chromeos_root,
                                    command,
                                    return_output=True)
  if ret != 0:
    raise ValueError("Board %s is invalid!" % board)
  # Remove ANSI escape sequences.
  out = StripANSIEscapeSequences(out)
  return out.strip()


def StripANSIEscapeSequences(string):
  string = re.sub(r"\x1b\[[0-9]*[a-zA-Z]", "", string)
  return string


def GetChromeSrcDir():
  return "var/cache/distfiles/target/chrome-src/src"


def GetEnvStringFromDict(env_dict):
  return " ".join(["%s=\"%s\"" % var for var in env_dict.items()])


def MergeEnvStringWithDict(env_string, env_dict, prepend=True):
  """Merge env string with dict."""
  if not env_string.strip():
    return GetEnvStringFromDict(env_dict)
  override_env_list = []
  ce = command_executer.GetCommandExecuter()
  for k, v in env_dict.items():
    v = v.strip("\"'")
    if prepend:
      new_env = "%s=\"%s $%s\"" % (k, v, k)
    else:
      new_env = "%s=\"$%s %s\"" % (k, k, v)
    command = "; ".join([env_string, new_env, "echo $%s" % k])
    ret, out, _ = ce.RunCommand(command, return_output=True)
    override_env_list.append("%s=%r" % (k, out.strip()))
  ret = env_string + " " + " ".join(override_env_list)
  return ret.strip()


def GetAllImages(chromeos_root, board):
  ce = command_executer.GetCommandExecuter()
  command = ("find %s/src/build/images/%s -name chromiumos_test_image.bin" %
             (chromeos_root, board))
  ret, out, _ = ce.RunCommand(command, return_output=True)
  assert ret == 0, "Could not run command: %s" % command
  return out.splitlines()


def AcquireLock(lock_file, timeout=1200):
  """Acquire a lock with timeout."""
  start_time = time.time()
  locked = False
  abs_path = os.path.abspath(lock_file)
  dir_path = os.path.dirname(abs_path)
  sleep_time = min(10, timeout/10.0)
  reason = "pid: {0}, commad: {1}".format(os.getpid(),
                                          sys.argv[0])
  if not os.path.exists(dir_path):
    try:
      with lock_machine.FileCreationMask(0002):
        os.makedirs(dir_path)
    except OSError:
      print "Cannot create dir {0}, exiting...".format(dir_path)
      exit(0)
  while True:
    locked = (lock_machine.Lock(lock_file).NonBlockingLock(True, reason))
    if locked:
      break
    time.sleep(sleep_time)
    if time.time() - start_time > timeout:
      logger.GetLogger().LogWarning(
          "Could not acquire lock on this file: {0} within {1} seconds."
          "Manually remove the file if you think the lock is stale"
          .format(abs_path, timeout))
      break
  return locked


def ReleaseLock(lock_file):
  lock_file = os.path.abspath(lock_file)
  ret = lock_machine.Lock(lock_file).Unlock(True)
  assert ret, ("Could not unlock {0},"
               "Please remove it manually".format(lock_file))


def IsFloat(text):
  if text is None:
    return False
  try:
    float(text)
    return True
  except ValueError:
    return False

def RemoveChromeBrowserObjectFiles(chromeos_root, board):
  """ Remove any object files from all the posible locations """
  out_dir = os.path.join(
      GetChrootPath(chromeos_root),
      "var/cache/chromeos-chrome/chrome-src/src/out_%s" % board)
  if os.path.exists(out_dir):
    shutil.rmtree(out_dir)
    logger.GetLogger().LogCmd("rm -rf %s" % out_dir)
  out_dir = os.path.join(
      GetChrootPath(chromeos_root),
      "var/cache/chromeos-chrome/chrome-src-internal/src/out_%s" % board)
  if os.path.exists(out_dir):
    shutil.rmtree(out_dir)
    logger.GetLogger().LogCmd("rm -rf %s" % out_dir)

@contextmanager
def WorkingDirectory(new_dir):
  """Get the working directory."""
  old_dir = os.getcwd()
  if old_dir != new_dir:
    msg = "cd %s" % new_dir
    logger.GetLogger().LogCmd(msg)
  os.chdir(new_dir)
  yield new_dir
  if old_dir != new_dir:
    msg = "cd %s" % old_dir
    logger.GetLogger().LogCmd(msg)
  os.chdir(old_dir)

def HasGitStagedChanges(git_dir):
  """Return True if git repository has staged changes."""
  command = 'cd {0} && git diff --quiet --cached --exit-code HEAD'.format(
    git_dir)
  return command_executer.GetCommandExecuter().RunCommand(
    command, print_to_console=False)

def HasGitUnstagedChanges(git_dir):
  """Return True if git repository has un-staged changes."""
  command = 'cd {0} && git diff --quiet --exit-code HEAD'.format(git_dir)
  return command_executer.GetCommandExecuter().RunCommand(
    command, print_to_console=False)

def HasGitUntrackedChanges(git_dir):
  """Return True if git repository has un-tracked changes."""
  command = 'cd {0} && test -z $(git ls-files --exclude-standard --others)' \
      .format(git_dir)
  return command_executer.GetCommandExecuter().RunCommand(
    command,print_to_console=False)

def IsGitTreeClean(git_dir):
  if HasGitStagedChanges(git_dir):
    logger.GetLogger().LogWarning("Git tree has staged changes.")
    return False
  if HasGitUnstagedChanges(git_dir):
    logger.GetLogger().LogWarning("Git tree has unstaged changes.")
    return False
  if HasGitUntrackedChanges(git_dir):
    logger.GetLogger().LogWarning("Git tree has un-tracked changes.")
    return False
  return True

def GetGitChangesAsList(git_dir, path=None, staged=False):
  command = 'cd {0} && git diff --name-only'.format(git_dir)
  if staged:
    command = command + ' --cached'
  if path:
    command = command + ' -- ' + path
  ec, out, err = command_executer.GetCommandExecuter().RunCommand(
    command, return_output=True, print_to_console=False)
  rv = []
  for line in out.splitlines():
    rv.append(line)
  return rv
