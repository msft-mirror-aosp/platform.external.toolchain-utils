#!/usr/bin/python

# Script to profile a page cycler, and get it back to the host.
import optparse
import os
import sys
import build_chrome_browser
import setup_chromeos
from utils import command_executer
from utils import utils


class FDOComparator(object):
  def __init__(self, board, remotes):
    self._board = board
    self._remotes = remotes
    self._chromeos_root = "chromeos"
    self._ce = command_executer.GetCommandExecuter()

  def _CheckoutChromeOS(self):
    if not os.path.exists(self._chromeos_root):
      setup_chromeos_args = ["--dir=%s" % self._chromeos_root,
                             "--minilayout"]
      setup_chromeos.Main(setup_chromeos_args)

  def _BuildChromeOSUsingBinaries(self):
    command = utils.GetSetupBoardCommand(self._board,
                                         usepkg=True)
    ret = self._ce.ChrootRunCommand(self._chromeos_root,
                                    command)
    if ret:
      raise Exception("Couldn't run setup_board!")
    command = utils.GetBuildPackagesCommand(self._board,
                                            True)
    ret = self._ce.ChrootRunCommand(self._chromeos_root,
                                    command)
    if ret:
      raise Exception("Couldn't run build_packages!")

  def _BuildChromeAndImage(self, env_dict):
    env_string = utils.GetEnvStringFromDict(env_dict)
    label = utils.GetFilenameFromString(env_string)
    if not utils.DoesLabelExist(self._chromeos_root, self._board, label):
      build_chrome_browser_args = ["--chromeos_root=%s" % self._chromeos_root,
                                   "--board=%s" % self._board,
                                   "--env=%s" %
                                   env_string]
      ret = build_chrome_browser.Main(build_chrome_browser_args)
      if ret:
        raise Exception("Couldn't build chrome browser!")
      utils.LabelLatestImage(self._chromeos_root, self._board, label)
    return label

  def _TestLabels(self, labels):
    experiment_file = "pgo_experiment.txt"
    experiment_header = """
    board: %s
    remote: %s
    """ % (self._board, self._remotes)
    experiment_tests = """
    benchmark: desktopui_PageCyclerTests {
      iterations: 5
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
               os.path.join(utils.GetImageDir(self._chromeos_root, self._board),
                            label,
                            "chromiumos_image.bin"))
        print >>f, experiment_image
    crosperf = os.path.join(os.path.dirname(__file__),
                            "..",
                            "crosperf",
                            "crosperf")
    command = "%s %s" % (crosperf, experiment_file)
    ret = self._ce.RunCommand(command)
    if ret:
      raise Exception("Couldn't run crosperf!")

  def DoAll(self):
    self._CheckoutChromeOS()
    self._BuildChromeOSUsingBinaries()
    vanilla_label = self._BuildChromeAndImage({"USE": "-pgo"})
    pgo_label = self._BuildChromeAndImage({"USE": "+pgo"})
    self._TestLabels([vanilla_label, pgo_label])
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
  options, _ = parser.parse_args(argv)
  if not options.board:
    print "Please give a board."
    return 1
  if not options.remote:
    print "Please give at least one remote machine."
    return 1
  fc = FDOComparator(options.board, options.remote)
  return fc.DoAll()


if __name__ == "__main__":
  retval = Main(sys.argv)
  sys.exit(retval)
