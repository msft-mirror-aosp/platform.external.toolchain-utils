#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.

"""Script to profile a page cycler, and get it back to the host."""

import copy
import optparse
import os
import pickle
import re
import sys
import tempfile
import time

import build_chrome_browser
import cros_login
import lock_machine
import run_tests
from utils import command_executer
from utils import logger
from utils import misc


class CyclerProfiler:
  REMOTE_TMP_DIR = "/tmp"
  TARBALL_FILE = "page_cycler.tar.gz"

  def __init__(self, chromeos_root, board, cycler, profile_dir, remote):
    self._chromeos_root = chromeos_root
    self._cycler = cycler
    self._profile_dir = profile_dir
    self._remote = remote
    self._board = board
    self._ce = command_executer.GetCommandExecuter()
    self._l = logger.GetLogger()

    self._gcov_prefix = os.path.join(self.REMOTE_TMP_DIR,
                                     self._GetProfileDir())

  def _GetProfileDir(self):
    return utils.GetCtargetFromBoard(self._board, self._chromeos_root)

  def _CopyTestData(self):
    tarball = os.path.join(self._chromeos_root,
                           "chroot",
                           "build",
                           self._board,
                           "usr",
                           "local",
                           "autotest",
                           "client",
                           "site_tests",
                           "desktopui_PageCyclerTests",
                           self.TARBALL_FILE)
    if not os.path.isfile(tarball):
      raise Exception("Tarball %s not found!" % tarball)
    self._ce.CopyFiles(tarball,
                       os.path.join(self.REMOTE_TMP_DIR, self.TARBALL_FILE),
                       dest_machine=self._remote,
                       chromeos_root=self._chromeos_root,
                       recursive=False,
                       dest_cros=True)

  def _PrepareTestData(self):
    # Extract the tarball
    command = "cd %s && tar xf %s" % (self.REMOTE_TMP_DIR, self.TARBALL_FILE)
    # chmod it
    self._ce.CrosRunCommand(command, chromeos_root=self._chromeos_root,
                            machine=self._remote)
    command = ("cd %s && find page_cycler -type f | xargs chmod a+r" %
               self.REMOTE_TMP_DIR)
    self._ce.CrosRunCommand(command, chromeos_root=self._chromeos_root,
                            machine=self._remote)
    command = ("cd %s && find page_cycler -type d | xargs chmod a+rx" %
               self.REMOTE_TMP_DIR)
    self._ce.CrosRunCommand(command, chromeos_root=self._chromeos_root,
                            machine=self._remote)

  def _GetRendererPID(self):
    # First get the renderer's pid.
    command = ("ps -f -u root --sort time | "
               "grep -v grep | "
               "grep renderer | "
               # Filter out disowned processes.
               r"grep -v '\b1\b' | "
               "tail -n1 |"
               "awk '{print $2}'")

    _, out, _ = self._ce.CrosRunCommand(command,
                                        chromeos_root=self._chromeos_root,
                                        machine=self._remote,
                                        return_output=True)
    pid = out.strip()
    return pid

  def _KillRemoteGDBServer(self):
    command = "pkill gdbserver"
    self._ce.CrosRunCommand(command,
                            chromeos_root=self._chromeos_root,
                            machine=self._remote)

  def _DumpRendererProfile(self):
    # Kill the remote GDB server if it is running.
    self._KillRemoteGDBServer()
    pid = self._GetRendererPID()
    if not pid:
      self._l.LogError("Could not find PID of renderer!")
      return
    # Copy the gdb_remote.dump file to the chromeos_root.
    gdb_file = "gdb_remote.dump"
    self._ce.CopyFiles(os.path.join(os.path.dirname(__file__),
                                    gdb_file),
                       os.path.join(self._chromeos_root,
                                    "src",
                                    "scripts",
                                    gdb_file),
                       recursive=False)
    command = ("./%s --remote_pid=%s "
               "--remote=%s "
               "--board=%s" %
               (gdb_file,
                pid,
                self._remote,
                self._board))
    self._ce.ChrootRunCommand(self._chromeos_root,
                              command,
                              command_timeout=60)
    # Kill the renderer now.
    self._KillRemotePID(pid)

  def _KillRemotePID(self, pid):
    command = "kill %s || kill -9 %s" % (pid, pid)
    self._ce.CrosRunCommand(command,
                            chromeos_root=self._chromeos_root,
                            machine=self._remote)

  def _CopyProfileToHost(self):
    dest_dir = os.path.join(self._profile_dir,
                            os.path.basename(self._gcov_prefix))
    # First remove the dir if it exists already
    if os.path.exists(dest_dir):
      command = "rm -rf %s" % dest_dir
      self._ce.RunCommand(command)

    # Strip out the initial prefix for the Chrome directory before doing the
    # copy.
    chrome_dir_prefix = misc.GetChromeSrcDir()

    command = "mkdir -p %s" % dest_dir
    self._ce.RunCommand(command)
    self._ce.CopyFiles(os.path.join(self._gcov_prefix,
                                    chrome_dir_prefix),
                       dest_dir,
                       src_machine=self._remote,
                       chromeos_root=self._chromeos_root,
                       recursive=True,
                       src_cros=True)

  def _RemoveRemoteProfileDir(self):
    command = "rm -rf %s" % self._gcov_prefix
    self._ce.CrosRunCommand(command, chromeos_root=self._chromeos_root,
                            machine=self._remote)

  def _LaunchCycler(self, cycler):
    command = ("DISPLAY=:0 "
               "XAUTHORITY=/home/chronos/.Xauthority "
               "GCOV_PREFIX=%s "
               "/opt/google/chrome/chrome "
               "--no-sandbox "
               "--user-data-dir=$(mktemp -d) "
               "--url \"file:///%s/page_cycler/data/page_cycler/%s/start.html?iterations=10&auto=1\" "
               "--enable-file-cookies "
               "--no-first-run "
               "--js-flags=expose_gc &" %
               (self._gcov_prefix,
                self.REMOTE_TMP_DIR,
                cycler))

    self._ce.CrosRunCommand(command, chromeos_root=self._chromeos_root,
                            machine=self._remote,
                            command_timeout=60)

  def _PkillChrome(self):
    command = "pkill chrome || pkill -9 chrome"
    self._ce.CrosRunCommand(command, chromeos_root=self._chromeos_root,
                            machine=self._remote)

  def DoProfile(self):
    # Copy the page cycler data to the remote
    self._CopyTestData()
    self._PrepareTestData()
    self._RemoveRemoteProfileDir()

    for cycler in self._cycler.split(","):
      self._ProfileOneCycler(cycler)

    # Copy the profile back
    self._CopyProfileToHost()

  def _ProfileOneCycler(self, cycler):
    # With aura, all that's needed is a stop/start ui.
    self._PkillChrome()
    cros_login.RestartUI(self._remote, self._chromeos_root, login=False)
    # Run the cycler
    self._LaunchCycler(cycler)
    # Get the renderer pid, and force dump its profile
    self._DumpRendererProfile()


def Main(argv):
  """The main function."""
  # Common initializations
###  command_executer.InitCommandExecuter(True)
  command_executer.InitCommandExecuter()
  l = logger.GetLogger()
  ce = command_executer.GetCommandExecuter()
  parser = optparse.OptionParser()
  parser.add_option("--cycler",
                    dest="cycler",
                    default="alexa_us",
                    help=("Comma-separated cyclers to profile. "
                          "Example: alexa_us,moz,moz2"
                          "Use all to profile all cyclers."))
  parser.add_option("--chromeos_root",
                    dest="chromeos_root",
                    default="../../",
                    help="Output profile directory.")
  parser.add_option("--board",
                    dest="board",
                    default="x86-zgb",
                    help="The target board.")
  parser.add_option("--remote",
                    dest="remote",
                    help=("The remote chromeos machine that"
                          " has the profile image."))
  parser.add_option("--profile_dir",
                    dest="profile_dir",
                    default="profile_dir",
                    help="Store profiles in this directory.")

  options, _ = parser.parse_args(argv)

  all_cyclers = ["alexa_us", "bloat", "dhtml", "dom",
                 "intl1", "intl2", "morejs", "morejsnp",
                 "moz", "moz2"]

  if options.cycler == "all":
    options.cycler = ",".join(all_cyclers)

  try:
    cp = CyclerProfiler(options.chromeos_root,
                        options.board,
                        options.cycler,
                        options.profile_dir,
                        options.remote)
    cp.DoProfile()
    retval = 0
  except Exception as e:
    retval = 1
    print e
  finally:
    print "Exiting..."
  return retval


if __name__ == "__main__":
  retval = Main(sys.argv)
  sys.exit(retval)
