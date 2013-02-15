#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to get past the login screen of ChromeOS.

"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import datetime
import fcntl
import getpass
import glob
import optparse
import os
import pickle
import socket
import sys
import time
from utils import logger
from utils import command_executer

LOGIN_PROMPT_VISIBLE_MAGIC_FILE = '/tmp/uptime-login-prompt-visible'
LOGGED_IN_MAGIC_FILE = '/var/run/state/logged-in'


login_script_contents="""
import os
import autox
import time

while True:
  print 'Waiting for login screen to appear...'
  if os.path.isfile('%s'):
    break
  time.sleep(1)
  print 'Done'

time.sleep(20)

xauth_filename = '/home/chronos/.Xauthority'
os.environ.setdefault('XAUTHORITY', xauth_filename)
os.environ.setdefault('DISPLAY', ':0.0')

print 'Now sending the hotkeys for logging in.'
ax = autox.AutoX()
# navigate to login screen
ax.send_hotkey('Ctrl+Shift+q')
ax.send_hotkey('Ctrl+Alt+l')
# escape out of any login screen menus (e.g., the network select menu)
time.sleep(2)
ax.send_hotkey('Escape')
time.sleep(2)
ax.send_hotkey('Tab')
time.sleep(0.5)
ax.send_hotkey('Tab')
time.sleep(0.5)
ax.send_hotkey('Tab')
time.sleep(0.5)
ax.send_hotkey('Tab')
time.sleep(0.5)
ax.send_hotkey('Return')
print 'Waiting for Chrome to appear...'
while True:
  if os.path.isfile('%s'):
    break
  time.sleep(1)
print 'Done'
"""

def LoginAsGuest(remote, chromeos_root):
  chromeos_root = os.path.expanduser(chromeos_root)
  ce = command_executer.GetCommandExecuter()
  # First, restart ui.
  command = 'rm -rf %s && stop ui && start ui' % LOGIN_PROMPT_VISIBLE_MAGIC_FILE
  ce.CrosRunCommand(command, machine=remote,
                    chromeos_root=chromeos_root)
  login_script = '/tmp/login.py'
  full_login_script_contents = (
      login_script_contents % (LOGIN_PROMPT_VISIBLE_MAGIC_FILE,
                               LOGGED_IN_MAGIC_FILE))
  with open(login_script, 'w') as f:
    f.write(full_login_script_contents)
  ce.CopyFiles(login_script,
               login_script,
               dest_machine=remote,
               chromeos_root=chromeos_root,
               recursive=False,
               dest_cros=True)
  return ce.CrosRunCommand('python %s' % login_script,
                           chromeos_root=chromeos_root,
                           machine=remote)


def Main(argv):
  """The main function."""
  parser = optparse.OptionParser()
  parser.add_option('-r',
                    '--remote',
                    dest='remote',
                    help='The remote ChromeOS box.')
  parser.add_option('-c',
                    '--chromeos_root',
                    dest='chromeos_root',
                    help='The ChromeOS root.')

  options, args = parser.parse_args(argv)

  return LoginAsGuest(options.remote, options.chromeos_root)

if __name__ == '__main__':
  retval = Main(sys.argv)
  return retval
