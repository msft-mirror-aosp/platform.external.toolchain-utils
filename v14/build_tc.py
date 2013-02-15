#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to build the ChromeOS toolchain.

This script sets up the toolchain if you give it the gcctools directory.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import getpass
import optparse
import sys
import tc_enter_chroot
from utils import utils

# Common initializations
(rootdir, basename) = utils.GetRoot(sys.argv[0])
utils.InitLogger(rootdir, basename)


def Main():
  """The main function."""
  parser = optparse.OptionParser()
  parser.add_option("-c", "--chromeos_root", dest="chromeos_root",
                    default="../..",
                    help="ChromeOS root checkout directory.")
  parser.add_option("-t", "--toolchain_root", dest="toolchain_root",
                    help="Toolchain root directory.")
  parser.add_option("-b", "--board", dest="board", default="x86-generic",
                    help="board is the argument to the setup_board command.")
  parser.add_option("-C", "--clean", dest="clean", default=False,
                    action="store_true",
                    help="Uninstall the toolchain.")
  parser.add_option("-f", "--force", dest="force", default=False,
                    action="store_true",
                    help="Do an uninstall/install cycle.")
  parser.add_option("-i", "--incremental", dest="incremental",
                    help="The toolchain component that should be "
                    "incrementally compiled.")
  parser.add_option("-B", "--binary", dest="binary",
                    action="store_true", default=False,
                    help="The toolchain should use binaries stored in "
                    "the install/ directory.")

  options = parser.parse_args()[0]

  if options.toolchain_root is None or options.board is None:
    parser.print_help()
    sys.exit()

  portage_flags = ""
  if options.binary == True:
    # FIXME(asharif): This should be using --usepkg but that was not working.
    portage_flags = "--usepkgonly"

  f = open(options.chromeos_root + "/src/overlays/overlay-" +
           options.board + "/toolchain.conf", "r")
  target = f.read()
  f.close()
  target = target.strip()
  features = "noclean userfetch userpriv usersandbox -strict"
  if options.incremental is not None and options.incremental:
    features += " keepwork"
  env = CreateEnvVarString(" FEATURES", features)
  env += CreateEnvVarString(" PORTAGE_USERNAME", getpass.getuser())
  version_number = utils.GetRoot(rootdir)[1]
  version_dir = "/usr/local/toolchain_root/" + version_number
  env += CreateEnvVarString(" PORT_LOGDIR", version_dir + "/logs")
  env += CreateEnvVarString(" PKGDIR", version_dir + "/pkgs")
  env += CreateEnvVarString(" PORTAGE_BINHOST", version_dir + "/pkgs")
  env += CreateEnvVarString(" PORTAGE_TMPDIR", version_dir + "/objects")
  env += CreateEnvVarString(" USE", "mounted_sources")

  retval = 0
  if options.force == True:
    retval = BuildTC(options.chromeos_root, options.toolchain_root, env,
                     target, True, options.incremental, portage_flags)
  retval = BuildTC(options.chromeos_root, options.toolchain_root, env,
                   target, options.clean, options.incremental, portage_flags)
  utils.AssertTrue(retval == 0, "Build toolchain failed!")

  if options.incremental is None and not options.clean:
    install_dir = rootdir + "/install"
    package_dir = (rootdir + "/pkgs/")
    retval = InstallTC(package_dir, install_dir)
    utils.AssertTrue(retval == 0, "Installation of the toolchain failed!")

  return retval


def CreateCrossdevPortageFlags(portage_flags):
  portage_flags = portage_flags.strip()
  if not portage_flags:
    return ""
  crossdev_flags = " --portage "
  crossdev_flags += " --portage ".join(portage_flags.split(" "))
  return crossdev_flags


def CreateEnvVarString(variable, value):
  return variable + "=" + EscapeQuoteString(value)


def EscapeQuoteString(string):
  return "\\\"" + string + "\\\""


def InstallTC(package_dir, install_dir):
  command = ("mkdir -p " + install_dir)
  command += ("&& for f in $(find " + package_dir +
              " -name \\*.tbz2); do tar xvf $f -C " +
              install_dir + "; done")
  retval = utils.RunCommand(command)
  return retval


def BuildTC(chromeos_root, toolchain_root, env, target, uninstall,
            incremental_component, portage_flags):
  """Build the toolchain."""
  portage_flags = portage_flags.strip()
  portage_flags += " -b "

  binutils_version = "2.20.1-r1"
  gcc_version = "9999"
  libc_version = "2.10.1-r1"
  kernel_version = "2.6.30-r1"

  sys.argv = ["--chromeos_root=" + chromeos_root,
              "--toolchain_root=" + toolchain_root]

  env += " "

  if uninstall == True:
    tflag = " -C "
  else:
    tflag = " -t "

  command = "sudo " + env

  if uninstall == True:
    command += " crossdev " + tflag + target
    sys.argv.append(command)
    retval = tc_enter_chroot.Main()
    return retval

  if incremental_component == "binutils":
    command += (" emerge =cross-" + target + "/binutils-" + binutils_version +
                portage_flags)
  elif incremental_component == "gcc":
    command += (" emerge =cross-" + target + "/gcc-" + gcc_version +
                portage_flags)
  elif incremental_component == "libc" or incremental_component == "glibc":
    command += (" emerge =cross-" + target + "/glibc-" + libc_version +
                portage_flags)
  else:
    crossdev_flags = CreateCrossdevPortageFlags(portage_flags)
    command += (" crossdev -v " + tflag + target +
                " --binutils " + binutils_version +
                " --libc " + libc_version +
                " --gcc " + gcc_version +
                " --kernel " + kernel_version +
                crossdev_flags)

  sys.argv.append(command)
  retval = tc_enter_chroot.Main()
  return retval

if __name__ == "__main__":
  Main()

