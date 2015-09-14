#!/usr/bin/python

# Script to test different toolchains against ChromeOS benchmarks.
import datetime
import optparse
import os
import sys
import build_chromeos
import setup_chromeos
import time
from utils import command_executer
from utils import misc
from utils import logger


CROSTC_ROOT = "/usr/local/google/crostc"
AFDO_BOARDS = ["butterfly", "lumpy", "stumpy", "stout", "parrot", "parrot_ivb"]
MAIL_PROGRAM = "~/var/bin/mail-sheriff"
WEEKLY_REPORTS_ROOT = os.path.join(CROSTC_ROOT, "weekly_test_data")
PENDING_ARCHIVES_DIR = os.path.join(CROSTC_ROOT, "pending_archives")
NIGHTLY_TESTS_DIR = os.path.join(CROSTC_ROOT, "nightly_test_reports")

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
    self._build_num = None

  def _DeleteChroot(self):
    command = "cd %s; cros_sdk --delete" % self._chromeos_root
    return self._ce.RunCommand(command)

  def _DeleteCcahe(self):
    # crosbug.com/34956
    command = "sudo rm -rf %s" % os.path.join(self._chromeos_root, ".cache")
    return self._ce.RunCommand(command)

  def _GetBuildNumber(self):
    """ This function assumes a ChromeOS image has been built in the chroot.
    It translates the 'latest' symlink in the
    <chroot>/src/build/images/<board> directory, to find the actual
    ChromeOS build number for the image that was built.  For example, if
    src/build/image/lumpy/latest ->  R37-5982.0.2014_06_23_0454-a1, then
    This function would parse it out and assign 'R37-5982' to self._build_num.
    This is used to determine the official, vanilla build to use for
    comparison tests.
    """
    # Get the path to 'latest'
    sym_path = os.path.join (misc.GetImageDir(self._chromeos_root,
                                              self._board),
                             "latest")
    # Translate the symlink to its 'real' path.
    real_path = os.path.realpath(sym_path)
    # Break up the path and get the last piece
    # (e.g. 'R37-5982.0.2014_06_23_0454-a1"
    path_pieces = real_path.split("/")
    last_piece = path_pieces[-1]
    # Break this piece into the image number + other pieces, and get the
    # image number [ 'R37-5982', '0', '2014_06_23_0454-a1']
    image_parts = last_piece.split(".")
    self._build_num = image_parts[0]

  def _BuildAndImage(self, label=""):
    if (not label or
        not misc.DoesLabelExist(self._chromeos_root, self._board, label)):
      build_chromeos_args = [build_chromeos.__file__,
                             "--chromeos_root=%s" % self._chromeos_root,
                             "--board=%s" % self._board,
                             "--rebuild"]
      if self._public:
        build_chromeos_args.append("--env=USE=-chrome_internal")

      if self._board in AFDO_BOARDS:
        build_chromeos_args.append("--env=USE=afdo_use")

      ret = build_chromeos.Main(build_chromeos_args)
      if ret != 0:
        raise RuntimeError("Couldn't build ChromeOS!")

      if not  self._build_num:
        self._GetBuildNumber()
      # Check to see if we need to create the symbolic link for the vanilla
      # image, and do so if appropriate.
      if not misc.DoesLabelExist(self._chromeos_root, self._board, "vanilla"):
        build_name = "%s-release/%s.0.0" % (self._board, self._build_num)
        full_vanilla_path = os.path.join (os.getcwd(), self._chromeos_root,
                                          'chroot/tmp', build_name)
        misc.LabelLatestImage(self._chromeos_root, self._board, label,
                              full_vanilla_path)
      else:
        misc.LabelLatestImage(self._chromeos_root, self._board, label)
    return label

  def _SetupBoard(self, env_dict, usepkg_flag, clobber_flag):
    env_string = misc.GetEnvStringFromDict(env_dict)
    command = ("%s %s" %
               (env_string,
                misc.GetSetupBoardCommand(self._board,
                                          usepkg=usepkg_flag,
                                          force=clobber_flag)))
    ret = self._ce.ChrootRunCommand(self._chromeos_root,
                                    command)
    error_str = "Could not setup board: '%s'" % command
    assert ret == 0, error_str

  def _UnInstallToolchain(self):
    command = ("sudo CLEAN_DELAY=0 emerge -C cross-%s/gcc" %
               misc.GetCtargetFromBoard(self._board,
                                   self._chromeos_root))
    ret = self._ce.ChrootRunCommand(self._chromeos_root,
                                    command)
    if ret != 0:
      raise RuntimeError("Couldn't uninstall the toolchain!")

  def _CheckoutChromeOS(self):
    # TODO(asharif): Setup a fixed ChromeOS version (quarterly snapshot).
    if not os.path.exists(self._chromeos_root):
      setup_chromeos_args = [setup_chromeos.__file__,
                             "--dir=%s" % self._chromeos_root]
      if self._public:
        setup_chromeos_args.append("--public")
      ret = setup_chromeos.Main(setup_chromeos_args)
      if ret != 0:
        raise RuntimeError("Couldn't run setup_chromeos!")


  def _BuildToolchain(self, config):
    # Call setup_board for basic, vanilla setup.
    self._SetupBoard({}, usepkg_flag=True, clobber_flag=False)
    # Now uninstall the vanilla compiler and setup/build our custom
    # compiler.
    self._UnInstallToolchain()
    envdict = {"USE": "git_gcc",
               "GCC_GITHASH": config.gcc_config.githash,
               "EMERGE_DEFAULT_OPTS": "--exclude=gcc"}
    self._SetupBoard(envdict, usepkg_flag=False, clobber_flag=False)


class ToolchainComparator(ChromeOSCheckout):
  def __init__(self, board, remotes, configs, clean,
               public, force_mismatch, noschedv2=False):
    self._board = board
    self._remotes = remotes
    self._chromeos_root = "chromeos"
    self._configs = configs
    self._clean = clean
    self._public = public
    self._force_mismatch = force_mismatch
    self._ce = command_executer.GetCommandExecuter()
    self._l = logger.GetLogger()
    timestamp = datetime.datetime.strftime(datetime.datetime.now(),
                                           "%Y-%m-%d_%H:%M:%S")
    self._reports_dir = os.path.join(NIGHTLY_TESTS_DIR,
        "%s.%s" % (timestamp, board),
        )
    self._noschedv2 = noschedv2
    ChromeOSCheckout.__init__(self, board, self._chromeos_root)


  def _FinishSetup(self):
    # Get correct .boto file
    current_dir = os.getcwd()
    src = "/usr/local/google/home/mobiletc-prebuild/.boto"
    dest = os.path.join(current_dir, self._chromeos_root,
                        "src/private-overlays/chromeos-overlay/"
                        "googlestorage_account.boto")
    # Copy the file to the correct place
    copy_cmd = "cp %s %s" % (src, dest)
    retval = self._ce.RunCommand(copy_cmd)
    if retval != 0:
      raise RuntimeError("Couldn't copy .boto file for google storage.")

    # Fix protections on ssh key
    command = ("chmod 600 /var/cache/chromeos-cache/distfiles/target"
               "/chrome-src-internal/src/third_party/chromite/ssh_keys"
               "/testing_rsa")
    retval = self._ce.ChrootRunCommand(self._chromeos_root, command)
    if retval != 0:
      raise RuntimeError("chmod for testing_rsa failed")

  def _TestLabels(self, labels):
    experiment_file = "toolchain_experiment.txt"
    image_args = ""
    if self._force_mismatch:
      image_args = "--force-mismatch"
    experiment_header = """
    board: %s
    remote: %s
    retries: 1
    """ % (self._board, self._remotes)
    experiment_tests = """
    benchmark: all_toolchain_perf {
      suite: telemetry_Crosperf
      iterations: 3
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
        crosperf_label = crosperf_label.replace(".", "")

        # Use the official build instead of building vanilla ourselves.
        if label == "vanilla":
          build_name = '%s-release/%s.0.0' % (self._board, self._build_num)

          # Now add 'official build' to test file.
          official_image = """
          official_image {
            chromeos_root: %s
            build: %s
          }
          """ % (self._chromeos_root, build_name)
          print >>f, official_image

        else:
          experiment_image = """
          %s {
            chromeos_image: %s
            image_args: %s
          }
          """ % (crosperf_label,
                 os.path.join(misc.GetImageDir(self._chromeos_root,
                                               self._board),
                              label, "chromiumos_test_image.bin"),
                 image_args)
          print >>f, experiment_image

    crosperf = os.path.join(os.path.dirname(__file__),
                            "crosperf",
                            "crosperf")
    noschedv2_opts = '--noschedv2' if self._noschedv2 else ''
    command = ("{crosperf} --no_email=True --results_dir={r_dir} "
               "--json_report=True {noschedv2_opts} {exp_file}").format(
                crosperf=crosperf,
                r_dir=self._reports_dir,
                noschedv2_opts=noschedv2_opts,
                exp_file=experiment_file)

    ret = self._ce.RunCommand(command)
    if ret != 0:
      raise RuntimeError("Couldn't run crosperf!")
    else:
      # Copy json report to pending archives directory.
      command = "cp %s/*.json %s/." % (self._reports_dir, PENDING_ARCHIVES_DIR)
      ret = self._ce.RunCommand(command)
    return


  def _CopyWeeklyReportFiles(self, labels):
    """Create tar files of the custom and official images and copy them
    to the weekly reports directory, so they exist when the weekly report
    gets generated.  IMPORTANT NOTE: This function must run *after*
    crosperf has been run; otherwise the vanilla images will not be there.
    """
    images_path = os.path.join(os.path.realpath(self._chromeos_root),
                               "src/build/images", self._board)
    weekday = time.strftime("%a")
    data_dir = os.path.join(WEEKLY_REPORTS_ROOT, self._board)
    dest_dir = os.path.join (data_dir, weekday)
    if not os.path.exists(dest_dir):
      os.makedirs(dest_dir)
    # Make sure dest_dir is empty (clean out last week's data).
    cmd = "cd %s; rm -Rf %s_*_image*" % (dest_dir, weekday)
    self._ce.RunCommand(cmd)
    # Now create new tar files and copy them over.
    for l in labels:
      test_path = os.path.join(images_path, l)
      if os.path.exists(test_path):
        if l != "vanilla":
          label_name = "test"
        else:
          label_name = "vanilla"
        tar_file_name = "%s_%s_image.tar" % (weekday, label_name)
        cmd = ("cd %s; tar -cvf %s %s/chromiumos_test_image.bin; "
               "cp %s %s/.") % (images_path,
                                tar_file_name,
                                l, tar_file_name,
                                dest_dir)
        tar_ret = self._ce.RunCommand(cmd)
        if tar_ret != 0:
          self._l.LogOutput("Error while creating/copying test tar file(%s)."
                            % tar_file_name)

  def _SendEmail(self):
    """Find email msesage generated by crosperf and send it."""
    filename = os.path.join(self._reports_dir, "msg_body.html")
    if (os.path.exists(filename) and
        os.path.exists(os.path.expanduser(MAIL_PROGRAM))):
      command = ('cat %s | %s -s "Nightly test results, %s" -team -html'
                 % (filename, MAIL_PROGRAM, self._board))
      self._ce.RunCommand(command)

  def DoAll(self):
    self._CheckoutChromeOS()
    labels = []
    labels.append("vanilla")
    for config in self._configs:
      label = misc.GetFilenameFromString(config.gcc_config.githash)
      if (not misc.DoesLabelExist(self._chromeos_root,
                                  self._board,
                                  label)):
        self._BuildToolchain(config)
        label = self._BuildAndImage(label)
      labels.append(label)
    self._FinishSetup()
    self._TestLabels(labels)
    self._SendEmail()
    # Only try to copy the image files if the test runs ran successfully.
    self._CopyWeeklyReportFiles(labels)
    if self._clean:
      ret = self._DeleteChroot()
      if ret != 0:
        return ret
      ret = self._DeleteCcahe()
      if ret != 0:
        return ret
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
  parser.add_option("--force-mismatch",
                    dest="force_mismatch",
                    default="",
                    help="Force the image regardless of board mismatch")
  parser.add_option("--noschedv2",
                    dest="noschedv2",
                    action="store_true",
                    default=False,
                    help="Pass --noschedv2 to crosperf.")
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
                           options.clean, options.public,
                           options.force_mismatch,
                           options.noschedv2)
  return fc.DoAll()


if __name__ == "__main__":
  retval = Main(sys.argv)
  sys.exit(retval)
