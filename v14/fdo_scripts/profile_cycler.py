#!/usr/bin/python

# Script to profile a page cycler, and get it back to the host.
import copy
import cros_login
import optparse
import os
import pickle
import re
import sys
import build_chrome_browser
import lock_machine
import run_tests
import tempfile
import time
from utils import command_executer
from utils import logger
from utils import utils


class CyclerProfiler:
  REMOTE_TMP_DIR = "/tmp"
  TARBALL_FILE = "page_cycler.tar.gz"

  def __init__(self, chromeos_root, board, cycler, profiles_dir, remote):
    self._chromeos_root = chromeos_root
    self._cycler = cycler
    self._profiles_dir = profiles_dir
    self._remote = remote
    self._board = board
    self._ce = command_executer.GetCommandExecuter()
    self._l = logger.GetLogger()

    self._gcov_prefix = os.path.join(self.REMOTE_TMP_DIR,
                                     self._GetProfileDir())

  def _GetProfileDir(self):
    profile_dir = self._cycler
    return profile_dir.replace(",", ".")

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
                              command)
    # Kill the renderer now.
    self._KillRemotePID(pid)

  def _KillRemotePID(self, pid):
    command = "kill %s || kill -9 %s" % (pid, pid)
    self._ce.CrosRunCommand(command,
                            chromeos_root=self._chromeos_root,
                            machine=self._remote)

  def _CopyProfileToHost(self):
    dest_dir = os.path.join(self._profiles_dir,
                            os.path.basename(self._gcov_prefix))
    # First remove the dir if it exists already
    if os.path.exists(dest_dir):
      command = "rm -rf %s" % dest_dir
      self._ce.RunCommand(command)

    # Strip out the initial prefix for the Chrome directory before doing the
    # copy.
    chrome_dir_prefix = "var/lib/portage/distfiles-target/chrome-src/src"

    command = "mkdir -p %s" % dest_dir
    self._ce.RunCommand(command)
    self._ce.CopyFiles(os.path.join(self._gcov_prefix,
                                    chrome_dir_prefix),
                       dest_dir,
                       src_machine=self._remote,
                       chromeos_root=self._chromeos_root,
                       recursive=True,
                       src_cros=True)

  def _LaunchCycler(self, cycler):
    # Remove the profile directory before launching Chrome.
    command = "rm -rf %s" % self._gcov_prefix
    self._ce.CrosRunCommand(command, chromeos_root=self._chromeos_root,
                            machine=self._remote)

    # Now run the actual command for profiling.
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
                            command_timeout=10)

  def DoProfile(self):
    # Copy the page cycler data to the remote
    self._CopyTestData()
    self._PrepareTestData()

    for cycler in self._cycler.split(","):
      self._ProfileOneCycler(cycler)

    # Copy the profile back
    self._CopyProfileToHost()

  def _ProfileOneCycler(self, cycler):
    # Get past the login screen of the remote
    cros_login.LoginAsGuest(self._remote, self._chromeos_root)
    # Run the cycler
    self._LaunchCycler(cycler)
    # Sleep for 60 seconds
    time.sleep(60)
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
  parser.add_option("--profiles_dir",
                    dest="profiles_dir",
                    default="profiles_dir",
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
                        options.profiles_dir,
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
