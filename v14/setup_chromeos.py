#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to checkout the ChromeOS source.

This script sets up the ChromeOS source in the given directory, matching a
particular release of ChromeOS.
"""

__author__ = "raymes@google.com (Raymes Khoury)"

import getpass
import optparse
import os
import sys
from utils import command_executer

GCLIENT_FILE = """solutions = [
  { "name"        : "CHROME_DEPS",
    "url"         :
    "svn://svn.chromium.org/chrome-internal/trunk/tools/buildspec/releases/%s",
    "custom_deps" : {
      "src/third_party/WebKit/LayoutTests": None,
      "src-pdf": None,
      "src/pdf": None,
    },
    "safesync_url": "",
   },
]
"""

# Common initializations
cmd_executer = None

GIT_TAGS_CMD = ("git ls-remote --tags "
                "ssh://git@gitrw.chromium.org:9222/chromiumos-overlay.git | "
                "grep refs/tags/ | grep '[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*' | "
                "cut -d '/' -f 3")


def StoreFile(filename, contents):
  f = open(filename, "w")
  f.write(contents)
  f.close()


def Usage(parser):
  parser.print_help()
  sys.exit(0)


def GetTags():
  res = cmd_executer.RunCommand(GIT_TAGS_CMD, True)
  return res[1].strip().split("\n")


def GetLatestTag(tags):
  latest = tags[0]
  for tag in tags:
    current_components = tag.split(".")
    latest_components = latest.split(".")
    for i in range(len(current_components)):
      if int(current_components[i]) > int(latest_components[i]):
        latest = tag
        break
      elif int(current_components[i]) < int(latest_components[i]):
        break

  return latest


def Main(argv):
  """Checkout the ChromeOS source."""
  global cmd_executer
  cmd_executer = command_executer.GetCommandExecuter()
  parser = optparse.OptionParser()
  parser.add_option("--dir", dest="directory",
                    help="Target directory for ChromeOS installation.")
  parser.add_option("--version", dest="version", default="latest",
                    help="""ChromeOS version. Can be: (1) A release version
in the format: 'X.X.X.X' (2) 'latest' for the latest release version or (3)
'top' for top of trunk. Default is 'latest'""")
  parser.add_option("--minilayout", dest="minilayout", default=False,
                    action="store_true",
                    help="""Whether to checkout the minilayout 
(smaller checkout).'""")

  options = parser.parse_args(argv)[0]

  tags = GetTags()

  if options.version == "latest":
    version = GetLatestTag(tags)
    print version
  elif options.version == "top":
    version = "top"
  elif options.version is None:
    print "No version specified"
    Usage(parser)
  else:
    version = options.version.strip()

  if not version in tags and version != "top":
    print "Version: '" + version + "' does not exist"
    Usage(parser)

  if options.directory is None:
    print "Please give a valid directory"
    Usage(parser)

  directory = options.directory.strip()

  if version == "top":
    branch = "master"
  else:
    branch = ".".join(version.split(".")[0:-1]) + ".B"

  # Don't checkout chrome sources outside the chroot at the moment.
  # If we check them out outside, we can't do some things, like build tests.
  checkout_chrome_outside_chroot = False

  minilayout = ""
  if options.minilayout == True:
    minilayout = " -m minilayout.xml"
  commands = []
  commands.append("mkdir -p " + directory)
  commands.append("cd " + directory)
  commands.append("repo init -u "
                  "ssh://git@gitrw.chromium.org:9222/manifest-internal -b "
                  + branch + minilayout)
  commands.append("repo sync -j10")
  if branch != "master":
    commands.append("repo forall -c 'git checkout -f -b %s %s'"
                    % (branch, version))
  cmd_executer.RunCommands(commands)

  # Setup svn credentials for use inside the chroot
  if getpass.getuser() == "mobiletc-prebuild":
    chromium_username = "raymes"
  else:
    chromium_username = "$USER"
  cmd_executer.RunCommand("svn ls --config-option config:auth:password-stores= "
                          "--config-option "
                          "servers:global:store-plaintext-passwords=yes "
                          "--username " + chromium_username + "@google.com "
                          "svn://svn.chromium.org/leapfrog-internal "
                          "svn://svn.chromium.org/chrome "
                          "svn://svn.chromium.org/chrome-internal > /dev/null")

  if checkout_chrome_outside_chroot:
    # Find Chrome browser version
    chrome_version = cmd_executer.RunCommand("%s/src/scripts/"
                                             "chromeos_version.sh | "
                                             "grep CHROME_BUILD"
                                             % directory, True)

    chrome_version = chrome_version[1].strip().split("=")
    if len(chrome_version) == 2:
      chrome_version = chrome_version[1]
    else:
      chrome_version = ""

    # Checkout chrome
    cmd_executer.RunCommand("mkdir -p %s/chrome_browser/" % directory)
    gclient_file = GCLIENT_FILE % chrome_version
    StoreFile(os.path.expanduser("%s/chrome_browser/.gclient"
                                 % directory), gclient_file)
    commands = []
    commands.append("cd " + options.directory)
    commands.append("cd chrome_browser")
    commands.append("gclient sync -v --nohooks --delete_unversioned_trees")
    cmd_executer.RunCommands(commands)

  print "Done"


if __name__ == "__main__":
  Main(sys.argv)
