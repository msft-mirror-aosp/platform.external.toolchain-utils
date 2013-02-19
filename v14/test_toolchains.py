#!/usr/bin/python

# Script to test different toolchains against ChromeOS benchmarks.
import optparse
import os
import sys
import build_chromeos
import setup_chromeos
from utils import command_executer
from utils import misc
from utils import logger


class GCCConfig(object):
  def __init__(self, githash):
    self.githash = githash


class ToolchainConfig:
  def __init__(self, gcc_config=None, binutils_config=None):
    self.gcc_config = gcc_config


class ChromeOSCheckout(object):
  def __init__(self, board, chromeos_root):
    self._board = board
    self._chromeos_root = chromeos_root
    self._ce = command_executer.GetCommandExecuter()
    self._l = logger.GetLogger()

  def _DeleteChroot(self):
    command = "cd %s; cros_sdk --delete" % self._chromeos_root
    return self._ce.RunCommand(command)

  def _BuildAndImage(self, label=""):
    if (not label or
        not misc.DoesLabelExist(self._chromeos_root, self._board, label)):
      build_chromeos_args = [build_chromeos.__file__,
                             "--chromeos_root=%s" % self._chromeos_root,
                             "--board=%s" % self._board,
                             "--rebuild"]
      if self._public:
        build_chromeos_args.append("--env=USE=-chrome_internal")
      ret = build_chromeos.Main(build_chromeos_args)
      if ret:
        raise Exception("Couldn't build ChromeOS!")
      if label:
        misc.LabelLatestImage(self._chromeos_root, self._board, label)
    return label

  def _SetupBoard(self, env_dict):
    env_string = misc.GetEnvStringFromDict(env_dict)
    command = ("%s %s" %
               (env_string,
                misc.GetSetupBoardCommand(self._board,
                                          usepkg=False)))
    ret = self._ce.ChrootRunCommand(self._chromeos_root,
                                    command)
    assert ret == 0, "Could not setup board with new toolchain."

  def _UnInstallToolchain(self):
    command = ("sudo CLEAN_DELAY=0 emerge -C cross-%s/gcc" %
               misc.GetCtargetFromBoard(self._board,
                                   self._chromeos_root))
    ret = self._ce.ChrootRunCommand(self._chromeos_root,
                                    command)
    if ret:
      raise Exception("Couldn't uninstall the toolchain!")

  def _CheckoutChromeOS(self):
    # TODO(asharif): Setup a fixed ChromeOS version (quarterly snapshot).
    if not os.path.exists(self._chromeos_root):
      setup_chromeos_args = [setup_chromeos.__file__,
                             "--dir=%s" % self._chromeos_root,
                             "--minilayout"]
      if self._public:
        setup_chromeos_args.append("--public")
      setup_chromeos.Main(setup_chromeos_args)

  def _BuildToolchain(self, config):
    self._UnInstallToolchain()
    self._SetupBoard({"USE": "git_gcc",
                      "GCC_GITHASH": config.gcc_config.githash,
                      "EMERGE_DEFAULT_OPTS": "--exclude=gcc"})


class ToolchainComparator(ChromeOSCheckout):
  def __init__(self, board, remotes, configs, clean, public):
    self._board = board
    self._remotes = remotes
    self._chromeos_root = "chromeos"
    self._configs = configs
    self._clean = clean
    self._public = public
    self._ce = command_executer.GetCommandExecuter()
    self._l = logger.GetLogger()
    ChromeOSCheckout.__init__(self, board, self._chromeos_root)

  def _TestLabels(self, labels):
    experiment_file = "toolchain_experiment.txt"
    experiment_header = """
    board: %s
    remote: %s
    """ % (self._board, self._remotes)
    experiment_tests = """
    benchmark: desktopui_PyAutoPerfTests {
      iterations: 1
    }
    """
    with open(experiment_file, "w") as f:
      print >>f, experiment_header
      print >>f, experiment_tests
      for label in labels:
        # TODO(asharif): Fix crosperf so it accepts labels with symbols
        crosperf_label = label
        crosperf_label = crosperf_label.replace("-", "minus")
        crosperf_label = crosperf_label.replace("+", "plus")
        experiment_image = """
        %s {
          chromeos_image: %s
        }
        """ % (crosperf_label,
               os.path.join(misc.GetImageDir(self._chromeos_root, self._board),
                            label,
                            "chromiumos_test_image.bin"))
        print >>f, experiment_image
    crosperf = os.path.join(os.path.dirname(__file__),
                            "crosperf",
                            "crosperf")
    command = "%s --email=c-compiler-chrome %s" % (crosperf, experiment_file)
    ret = self._ce.RunCommand(command)
    if ret:
      raise Exception("Couldn't run crosperf!")

  def DoAll(self):
    self._CheckoutChromeOS()
    labels = []
    vanilla_label = self._BuildAndImage("vanilla")
    labels.append(vanilla_label)
    for config in self._configs:
      label = misc.GetFilenameFromString(config.gcc_config.githash)
      if (not misc.DoesLabelExist(self._chromeos_root,
                                  self._board,
                                  label)):
        self._BuildToolchain(config)
        label = self._BuildAndImage(label)
      labels.append(label)
    self._TestLabels(labels)
    if self._clean:
      ret = self._DeleteChroot()
      if ret: return ret
    return 0


def Main(argv):
  """The main function."""
  # Common initializations
###  command_executer.InitCommandExecuter(True)
  command_executer.InitCommandExecuter()
  parser = optparse.OptionParser()
  parser.add_option("--remote",
                    dest="remote",
                    help="Remote machines to run tests on.")
  parser.add_option("--board",
                    dest="board",
                    default="x86-zgb",
                    help="The target board.")
  parser.add_option("--githashes",
                    dest="githashes",
                    default="master",
                    help="The gcc githashes to test.")
  parser.add_option("--clean",
                    dest="clean",
                    default=False,
                    action="store_true",
                    help="Clean the chroot after testing.")
  parser.add_option("--public",
                    dest="public",
                    default=False,
                    action="store_true",
                    help="Use the public checkout/build.")
  options, _ = parser.parse_args(argv)
  if not options.board:
    print "Please give a board."
    return 1
  if not options.remote:
    print "Please give at least one remote machine."
    return 1
  toolchain_configs = []
  for githash in options.githashes.split(","):
    gcc_config = GCCConfig(githash=githash)
    toolchain_config = ToolchainConfig(gcc_config=gcc_config)
    toolchain_configs.append(toolchain_config)
  fc = ToolchainComparator(options.board, options.remote, toolchain_configs,
                           options.clean, options.public)
  return fc.DoAll()


if __name__ == "__main__":
  retval = Main(sys.argv)
  sys.exit(retval)
