#!/usr/bin/python
#
# Copyright Google Inc. 2014

import sys
import time
import optparse
import os

from utils import constants
from utils import command_executer

WEEKDAYS = ['Sat', 'Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri']

DATA_ROOT_DIR = os.path.join(constants.CROSTC_WORKSPACE,
                             'weekly_test_data')

EXPERIMENT_FILE = os.path.join(DATA_ROOT_DIR, 'weekly_report')


def Generate_Vanilla_Report_File(vanilla_image_paths, board, remote,
                                 chromeos_root, cmd_executer):

    experiment_header = """
name: weekly_vanilla_report
board: %s
remote: %s
""" % (board, remote)


    experiment_tests = """
benchmark: all_perfv2 {
  suite: telemetry_Crosperf
  iterations: 3
}
"""

    filename = "%s_%s_vanilla.exp" % (EXPERIMENT_FILE, board)
    if os.path.exists(filename):
        cmd = "rm %s" % filename
        cmd_executer.RunCommand(cmd)

    with open(filename, "w") as f:
        print >>f, experiment_header
        print >>f, experiment_tests

        # Add each vanilla image
        for test_path in vanilla_image_paths:
            pieces = test_path.split("/")
            test_name = pieces[-1]
            test_image = """
%s {
  chromeos_root: %s
  chromeos_image: %s
}
""" % (test_name, chromeos_root, os.path.join (test_path, "chromiumos_test_image.bin"))
            print >>f, test_image

    return filename

def Generate_Test_File(test_image_paths, vanilla_image_path, board, remote,
                       chromeos_root, cmd_executer):

    experiment_header = """
name: weekly_report
board: %s
remote: %s
""" % (board, remote)


    experiment_tests = """
benchmark: all_perfv2 {
  suite: telemetry_Crosperf
  iterations: 3
}
"""

    filename = "%s_%s.exp" % (EXPERIMENT_FILE, board)
    if os.path.exists(filename):
        cmd = "rm %s" % filename
        cmd_executer.RunCommand(cmd)

    with open(filename, "w") as f:
        print >>f, experiment_header
        print >>f, experiment_tests

        # Add vanilla image (first)
        vanilla_image = """
vanilla_image {
  chromeos_root: %s
  chromeos_image: %s
}
""" % (chromeos_root, os.path.join(vanilla_image_path, "chromiumos_test_image.bin"))

        print >>f, vanilla_image

        # Add each test image
        for test_path in test_image_paths:
            pieces = test_path.split("/")
            test_name = pieces[-1]
            test_image = """
%s {
  chromeos_root: %s
  chromeos_image: %s
}
""" % (test_name, chromeos_root, os.path.join (test_path, "chromiumos_test_image.bin"))
            print >>f, test_image

    return filename



def Main(argv):

    parser = optparse.OptionParser()
    parser.add_option('-b', '--board', dest='board',
                      help='Target board.')
    parser.add_option("-r", "--remote", dest="remote",
                    help="Target device.")
    parser.add_option("-v", "--vanilla_only", dest="vanilla_only",
                    action="store_true",
                    default=False,
                    help="Generate a report comparing only the vanilla images.")

    options = parser.parse_args(argv[1:])[0]

    if not options.board:
        print "Must specify a board."
        return 1

    if not options.remote:
        print "Must specify at least one remote."
        return 1

    cmd_executer = command_executer.GetCommandExecuter(log_level="average")

    # Find all the test image tar files, untar them and add them to
    # the list. Also find and untar vanilla image tar files, and keep
    # track of the first vanilla image.
    report_image_paths = []
    vanilla_image_paths = []
    first_vanilla_image = None
    for day in WEEKDAYS:
        data_path = os.path.join(DATA_ROOT_DIR, options.board, day)
        if os.path.exists(data_path):
            # First, untar the test image.
            tar_file_name = "%s_test_image.tar" % day
            tar_file_path = os.path.join(data_path, tar_file_name)
            image_dir = "%s_test_image" % day
            image_path = os.path.join(data_path, image_dir)
            if os.path.exists(tar_file_path):
                if not os.path.exists(image_path):
                    os.makedirs(image_path)
                cmd = ("cd %s; tar -xvf %s -C %s --strip-components 1" %
                       (data_path, tar_file_path, image_path))
                ret = cmd_executer.RunCommand(cmd)
                if not ret:
                    report_image_paths.append(image_path)
            # Next, untar the vanilla image.
            vanilla_file = "%s_vanilla_image.tar" % day
            v_file_path = os.path.join(data_path, vanilla_file)
            image_dir = "%s_vanilla_image" % day
            image_path = os.path.join(data_path, image_dir)
            if os.path.exists(v_file_path):
                if not os.path.exists(image_path):
                    os.makedirs(image_path)
                cmd = ("cd %s; tar -xvf %s -C %s --strip-components 1" %
                       (data_path, v_file_path, image_path))
                ret = cmd_executer.RunCommand(cmd)
                if not ret:
                    vanilla_image_paths.append(image_path)
                if not first_vanilla_image:
                    first_vanilla_image = image_path

    # Find a chroot we can use.  Look for a directory containing both
    # an experiment file and a chromeos directory (the experiment file will
    # only be created if both images built successfully, i.e. the chroot is
    # good).
    chromeos_root = None
    for day in WEEKDAYS:
        startdir = os.path.join(constants.CROSTC_WORKSPACE, day)
        num_dirs = os.listdir(startdir)
        for d in num_dirs:
            exp_file = os.path.join(startdir, d, "toolchain_experiment.txt")
            chroot = os.path.join(startdir, d, "chromeos")
            if os.path.exists(chroot) and os.path.exists(exp_file):
                chromeos_root = chroot
            if chromeos_root:
                break;
        if chromeos_root:
            break;

    if not chromeos_root:
        print "Unable to locate a usable chroot. Exiting without report."
        return 1


    # Create the Crosperf experiment file for generating the weekly report.
    if not options.vanilla_only:
        filename = Generate_Test_File (report_image_paths, first_vanilla_image,
                                       options.board, options.remote,
                                       chromeos_root, cmd_executer)
    else:
        filename = Generate_Vanilla_Report_File (vanilla_image_paths,
                                                 options.board, options.remote,
                                                 chromeos_root, cmd_executer)

    # Run Crosperf on the file to generate the weekly report.
    cmd = ("%s/toolchain-utils/crosperf/crosperf "
           "%s  --cache_only=True --email=c-compiler-chrome@google.com" %
           (constants.CROSTC_WORKSPACE, filename))
    retval = cmd_executer.RunCommand(cmd)
    return retval



if __name__ == '__main__':
    retval = Main(sys.argv)
    sys.exit(retval)
