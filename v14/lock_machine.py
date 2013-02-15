#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to lock/unlock machines.

"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import datetime
import getpass
import glob
import optparse
import os
import sys
import tc_enter_chroot
import build_chromeos
import setup_chromeos
import socket
from utils import command_executer
from utils import utils
from utils import logger


LOCK_DIR = "locks"
LOCK_USERNAME = "mobiletc-prebuild"
REASON_FILE = "reason.txt"
UMASK_COMMAND = "umask a+rwx"


# TODO(asharif): Use duration?
def LockMachine(machine, unlock=False, duration=None, reason=None):
  ce = command_executer.GetCommandExecuter()
  l = logger.GetLogger()
  locks_dir = os.path.join("/home", LOCK_USERNAME, LOCK_DIR)

  if not os.path.exists(locks_dir):
    l.LogError("Locks dir: %s must exist" % locks_dir)
    return 1

  machine_lock_dir = os.path.join(locks_dir, machine)

  if unlock:
    lock_program = "rm -r"
  else:
    lock_program = "%s && mkdir" % UMASK_COMMAND
  command = ("%s %s" %
             (lock_program,
              machine_lock_dir))
  retval = ce.RunCommand(command)
  if retval: return retval

  reason_file = os.path.join(machine_lock_dir, "reason.txt")
  if not unlock:
    if not reason:
      reason = ""
    full_reason = ("Locked by: %s on %s: %s" %
                   (getpass.getuser(),
                    str(datetime.datetime.now()),
                    reason))
    command = ("%s && echo \"%s\" > %s" %
               (UMASK_COMMAND,
                full_reason,
                reason_file))
    retval = ce.RunCommand(command)
    if retval: return retval

  return 0


def ListLocks(machine=None):
  if not machine:
    machine = "*"
  locks_dir = os.path.join("/home", LOCK_USERNAME, LOCK_DIR)
  print "Machine: Reason"
  print "---------------"
  for current_dir in glob.glob(os.path.join(locks_dir, machine)):
    f = open(os.path.join(current_dir, REASON_FILE))
    reason = f.read()
    reason = reason.strip()
    print "%s: %s" % (os.path.basename(current_dir), reason)
  return 0


def Main(argv):
  """The main function."""
  # Common initializations
  ce = command_executer.GetCommandExecuter()
  l = logger.GetLogger()

  parser = optparse.OptionParser()
  parser.add_option("-m",
                    "--machine",
                    dest="machine",
                    help="The machine to be locked.")
  parser.add_option("-r",
                    "--reason",
                    dest="reason",
                    help="The lock reason.")
  parser.add_option("-u",
                    "--unlock",
                    dest="unlock",
                    action="store_true",
                    default=False,
                    help="Use this to unlock.")
  parser.add_option("-l",
                    "--list_locks",
                    dest="list_locks",
                    action="store_true",
                    default=False,
                    help="Use this to list locks.")

  options = parser.parse_args(argv)[0]

  if not options.list_locks and not options.machine:
    l.LogError("Either --list_locks or --machine option is needed.")
    return 1

  machine = options.machine
  unlock = options.unlock
  reason = options.reason

  # Canonicalize machine name
  if machine:
    machine = socket.gethostbyaddr(machine)[0]

  if options.list_locks:
    retval = ListLocks(machine)
  else:
    retval = LockMachine(machine, unlock=unlock, reason=reason)
  return retval

if __name__ == "__main__":
  retval = Main(sys.argv)
  sys.exit(retval)
