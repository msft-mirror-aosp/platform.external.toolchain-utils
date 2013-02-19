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

def Usage(parser):
  parser.print_help()
  sys.exit(0)


def Main(argv):
  """Checkout the ChromeOS source."""
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
  parser.add_option("--public", "-p", dest="public", default=False,
                    action="store_true",
                    help="Use the public checkout instead of the private one.")

  options = parser.parse_args(argv)[0]

  if not options.version:
    parser.print_help()
    logger.GetLogger().LogFatal("No version specified.")
  else:
    version = options.version.strip()

  if not options.directory:
    parser.print_help()
    logger.GetLogger().LogFatal("No directory specified.")

  directory = options.directory.strip()

  if options.public:
    manifest_repo = "http://git.chromium.org/chromiumos/manifest.git"
    versions_repo = "http://git.chromium.org/chromiumos/manifest-versions.git"
  else:
    manifest_repo = (
        "ssh://gerrit-int.chromium.org:29419/chromeos/manifest-internal.git")
    versions_repo = (
        "ssh://gerrit-int.chromium.org:29419/chromeos/manifest-versions.git")

  if version in ["top", "latest"]:
    init = "repo init -u %s" % manifest_repo
    if options.minilayout:
      init += " -m minilayout.xml"
  else:
    version, manifest = version.split(".", 1)
    init = ("repo init -u %s -m paladin/buildspecs/%s/%s.xml" % (
        versions_repo, version, manifest))
  init += " --repo-url=http://git.chromium.org/external/repo.git"

  commands = ["mkdir -p %s" % directory,
              "cd %s" % directory,
              init,
              "repo sync -j %s" % options.jobs]
  cmd_executer = command_executer.GetCommandExecuter()
  ret = cmd_executer.RunCommands(commands)
  if ret:
    return ret

  # Setup svn credentials for use inside the chroot
  if getpass.getuser() == "mobiletc-prebuild":
    chromium_username = "raymes"
  else:
    chromium_username = "$USER"

  return cmd_executer.RunCommand(
      "svn ls --config-option config:auth:password-stores= "
      "--config-option "
      "servers:global:store-plaintext-passwords=yes "
      "--username " + chromium_username + "@google.com "
      "svn://svn.chromium.org/leapfrog-internal "
      "svn://svn.chromium.org/chrome "
      "svn://svn.chromium.org/chrome-internal > /dev/null")


if __name__ == "__main__":
  retval = Main(sys.argv)
  sys.exit(retval)
