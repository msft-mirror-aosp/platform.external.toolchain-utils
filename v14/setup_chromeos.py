#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to checkout the ChromeOS source.

This script sets up the ChromeOS source in the given directory, matching a
particular release of ChromeOS.
"""

__author__ = "raymes@google.com (Raymes Khoury)"

import optparse
import sys
from utils import utils

# Common initializations
(rootdir, basename) = utils.GetRoot(sys.argv[0])
utils.InitLogger(rootdir, basename)


GIT_TAGS_CMD = ("git ls-remote --tags "
                "ssh://git@gitrw.chromium.org:9222/chromiumos-overlay.git | "
                "grep refs/tags/ | grep '[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*' | "
                "cut -d '/' -f 3 | sort -nr")


def Usage(parser):
  parser.print_help()
  sys.exit(0)


def GetTags():
  res = utils.RunCommand(GIT_TAGS_CMD, True)
  return res[1].strip().split("\n")


def Main():
  """Checkout the ChromeOS source."""
  parser = optparse.OptionParser()
  parser.add_option("--dir", dest="directory",
                    help="Target directory for ChromeOS installation.")
  parser.add_option("--version", dest="version",
                    help="""ChromeOS version. Can be: (1) A release version
in the format: 'X.X.X.X' (2) 'latest' for the latest release version or (3)
'top' for top of trunk. Default is 'latest'""")

  tags = GetTags()

  options = parser.parse_args()[0]

  if options.version == "latest":
    version = tags[0]
    print version
  elif options.version == "top":
    version = ""
  elif options.version is None:
    Usage(parser)
  else:
    version = options.version.strip()

  if not version in tags:
    print "Version: '" + version + "' does not exist"
    Usage(parser)

  if options.directory is None:
    print "Please give a valid directory"
    Usage(parser)

  directory = options.directory.strip()

  branch = ".".join(version.split(".")[0:-1]) + ".B"

  commands = []
  commands.append("mkdir -p " + directory)
  commands.append("cd " + directory)
  commands.append("repo init -u "
                  "ssh://git@gitrw.chromium.org:9222/manifest-internal -b "
                  + branch)
  commands.append("repo sync -j10")
  commands.append("repo forall -c 'git checkout -f -b %s %s'"
                  % (branch, version))
  utils.RunCommands(commands)

  commands = []
  commands.append("cd " + directory + "/src/scripts")
  commands.append("./get_svn_repos.sh")
  utils.RunCommands(commands)

  print "Done"


if __name__ == "__main__":
  Main()
