#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to build the ChromeOS toolchain.

This script sets up the toolchain if you give it the gcctools directory.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import getpass
import optparse
import os
import sys
import tc_enter_chroot
import build_chromeos
import setup_chromeos
from utils import command_executer
from utils import utils
from utils import logger

# Common initializations
cmd_executer = command_executer.GetCommandExecuter()


def Main(argv):
  """The main function."""
  rootdir = utils.GetRoot(sys.argv[0])[0]

  parser = optparse.OptionParser()
  parser.add_option("-c", "--chromeos_root", dest="chromeos_root",
                    help=("ChromeOS root checkout directory" +
                           " uses ../.. if none given."))
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
  parser.add_option("-s", "--setup-chromeos-options",
                    dest="setup_chromeos_options",
                    help="Additional options that should be passed on to"
                    "the setup_chromeos script.")
  parser.add_option("-o", "--output", dest="output",
                    default=rootdir + "/output",
                    help="The output directory where logs,pkgs, etc. go.")

  options = parser.parse_args(argv)[0]

  if options.toolchain_root is None or options.board is None:
    parser.print_help()
    sys.exit()

  if options.chromeos_root is None:
    if os.path.exists("enter_chroot.sh"):
      options.chromeos_root = "../.."
    else:
      logger.GetLogger().LogError("--chromeos_root not given")
      parser.print_help()
      sys.exit()
  else:
    options.chromeos_root = os.path.expanduser(options.chromeos_root)

  if ((not os.path.exists(options.chromeos_root)) or
      (not os.path.exists(options.chromeos_root +
                          "/src/scripts/enter_chroot.sh"))):
    logger.GetLogger().LogOutput("Creating a chromeos checkout at: %s" %
                                 options.chromeos_root)
    sc_args = []
    sc_args.append("--minilayout")
    sc_args.append("--dir=%s" % options.chromeos_root)
    if options.setup_chromeos_options:
      sc_args.append(options.setup_chromeos_options)
    setup_chromeos.Main(sc_args)

  output = options.output

  if output.startswith("/") == False:
    output = os.getcwd() + "/" + output
  else:
    output = os.path.expanduser(output)

  chroot_mount = "/usr/local/toolchain_root/"
  chroot_base = utils.GetRoot(output)[1]
  chroot_output = chroot_mount + chroot_base

  tc_enter_chroot_options = []
  output_mount = ("--output=" + output)
  tc_enter_chroot_options.append(output_mount)

  build_chromeos.MakeChroot(options.chromeos_root)

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
  logdir = "/logs"
  pkgdir = "/pkgs"
  tmpdir = "/objects"
  installdir = "/install"
  package_dir = output + pkgdir
  portage_logdir = chroot_output + logdir
  portage_pkgdir = chroot_output + pkgdir
  portage_tmpdir = chroot_output + tmpdir
  env += CreateEnvVarString(" PORT_LOGDIR", portage_logdir)
  env += CreateEnvVarString(" PKGDIR", portage_pkgdir)
  env += CreateEnvVarString(" PORTAGE_BINHOST", portage_pkgdir)
  env += CreateEnvVarString(" PORTAGE_TMPDIR", portage_tmpdir)
  env += CreateEnvVarString(" USE", "mounted_sources")

  retval = 0
  if options.force == True:
    retval = BuildTC(options.chromeos_root, options.toolchain_root, env,
                     target, True, options.incremental, portage_flags,
                     tc_enter_chroot_options)
  retval = BuildTC(options.chromeos_root, options.toolchain_root, env,
                   target, options.clean, options.incremental, portage_flags,
                   tc_enter_chroot_options)
  utils.AssertTrue(retval == 0, "Build toolchain failed!")
  command = "sudo chown -R " + getpass.getuser() + " " + package_dir

  if options.incremental is None and not options.clean:
    install_dir = output + installdir
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
              " -name \\*.tbz2); do tar xf $f -C " +
              install_dir + " ; done")
  retval = cmd_executer.RunCommand(command)
  return retval


def BuildTC(chromeos_root, toolchain_root, env, target, uninstall,
            incremental_component, portage_flags, tc_enter_chroot_options):
  """Build the toolchain."""
  portage_flags = portage_flags.strip()
  portage_flags += " -b "

  binutils_version = "2.20.1-r1"
  gcc_version = "9999"
  libc_version = "2.10.1-r2"
  kernel_version = "2.6.30-r1"

  rootdir = utils.GetRoot(sys.argv[0])[0]
  argv = [rootdir + "/tc_enter_chroot.py",
          "--chromeos_root=" + chromeos_root,
          "--toolchain_root=" + toolchain_root]
  argv += tc_enter_chroot_options

  env += " "

  if uninstall == True:
    tflag = " -C "
  else:
    tflag = " -t "

  command = " -- sudo " + env

  if uninstall == True:
    command += " crossdev " + tflag + target
    argv.append(command)
    retval = tc_enter_chroot.Main(argv)
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

  argv.append(command)
  retval = tc_enter_chroot.Main(argv)
  return retval

if __name__ == "__main__":
  Main(sys.argv)

