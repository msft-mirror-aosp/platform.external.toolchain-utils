#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to checkout the ChromeOS source.

This script sets up the ChromeOS source in the given directory, matching a
particular release of ChromeOS.
"""

__author__ = "raymes@google.com (Raymes Khoury)"

import getpass
import multiprocessing
import optparse
import os
import sys
from utils import command_executer
from utils import logger

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

def StoreFile(filename, contents):
  f = open(filename, "w")
  f.write(contents)
  f.close()


def Usage(parser):
  parser.print_help()
  sys.exit(0)


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
  parser.add_option("--jobs", "-j", dest="jobs", default="1",
                    help="Number of repo sync threads to use.")

  options = parser.parse_args(argv)[0]

  if options.version == "latest":
    version = "latest"
  elif options.version == "top":
    version = "top"
  elif options.version is None:
    logger.GetLogger().LogError("No version specified.")
    Usage(parser)
  else:
    version = options.version.strip()

  if options.directory is None:
    logger.GetLogger().LogError("No directory specified.")
    Usage(parser)

  directory = options.directory.strip()

  if version == "top" or version == "latest":
    init = "repo init -u ssh://gerrit-int.chromium.org:29419/chromeos/manifest-internal.git"
    if options.minilayout ==  True:
      init += " -m minilayout.xml"
  else:
    init = ("repo init -u ssh://gerrit-int.chromium.org:29419/chromeos/manifest-versions.git "
            "-m buildspecs/%s/%s.xml" % (version[0:4], version))
  init += " --repo-url=http://git.chromium.org/external/repo.git"

  commands = []
  commands.append("mkdir -p " + directory)
  commands.append("cd " + directory)
  commands.append(init)
  commands.append("repo sync -j %s" % options.jobs)
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

  return 0


if __name__ == "__main__":
  retval = Main(sys.argv)
  sys.exit(retval)
