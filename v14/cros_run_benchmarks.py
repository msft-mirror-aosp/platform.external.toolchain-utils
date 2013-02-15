#!/usr/bin/python

"""
*** How to run benchmarks using two ChromeOS images and compare them ***

The relevant script here is cros_run_benchmarks.py. 

=== Pre-requisites ===

1. A chromeos_root where you have a ChromeOS checkout as well a chroot that has
autotests emerged for the particular board you are testing.
A chromeos_root will have a src/ and a chroot/ dir.
2. Multiple ChromeOS images that you want to compare. Make sure these images
have been modded for test (mod_image_for_test.sh). These images should be of the
same board as the one that has the autotests (though you can give a board
override on the command line).
3. A remote ChromeOS machine on which the tests will be done.

=== How to run ===

Specify the chromeos_root, the images and the remote machine. Optionally you can
also specify tests to run, iterations to run, etc. Here is an example:

python cros_scripts/cros_run_benchmarks.py --iterations=1 --tests=AesThroughput --remote=chromeos-test2 --images=/home/asharif/a/chromeos.latest.fdo/src/build/images/x86-generic/0.10.142.2011_01_18_1450-a1/chromiumos_image.bin,/home/asharif/a/chromeos.latest.fdo/src/build/images/x86-generic/0.10.142.2011_01_19_1120-a1/chromiumos_image.bin --chromeos_root=/home/asharif/a/chromeos.latest.fdo/ --board=x86-generic

=== Example explanation ===

I checked out chromeos sources in my --chromeos_root option. In there I did
make_chroot, setup_board, build_packages, build_image and mod_image_for_test
twice to obtain two images. The images were given to cros_run_benchmarks
separated by commas. The test I chose to run on both images is AesThroughput.
You would typically run BootPerfServer and PageCycler.


=== Example Output & Explanation ===

For my command line, it produced an output like:

OUTPUT: Benchmark: AesThroughput
Run labels: 
0: /usr/local/google/home/asharif/chromeos.latest.fdo/src/build/images/x86-generic/0.10.142.2011_01_18_1450-a1/chromiumos_image.bin 0.10.142.2011_01_18_1455 (Test Build 166caf1e - Tue Jan 18 14:55:39 PST 2011 - asharif) developer x86-generic
1: /usr/local/google/home/asharif/chromeos.latest.fdo/src/build/images/x86-generic/0.10.142.2011_01_19_1120-a1/chromiumos_image.bin 0.10.142.2011_01_19_1125 (Test Build 166caf1e - Wed Jan 19 11:25:33 PST 2011 - asharif) developer x86-generic
Group labels: 
0: /usr/local/google/home/asharif/chromeos.latest.fdo/src/build/images/x86-generic/0.10.142.2011_01_18_1450-a1/chromiumos_image.bin 0.10.142.2011_01_18_1455 (Test Build 166caf1e - Tue Jan 18 14:55:39 PST 2011 - asharif) developer x86-generic 
1: /usr/local/google/home/asharif/chromeos.latest.fdo/src/build/images/x86-generic/0.10.142.2011_01_19_1120-a1/chromiumos_image.bin 0.10.142.2011_01_19_1125 (Test Build 166caf1e - Wed Jan 19 11:25:33 PST 2011 - asharif) developer x86-generic latest

           Benchmark          0 (0)          1 (1) 
6_blocksz_1024_bytes 49592320 (+0%) 49684138 (+0%) 
256_blocksz_16_bytes 28907317 (+0%) 29669280 (+3%) 
56_blocksz_256_bytes 48225450 (+0%) 48199168 (-0%) 
256_blocksz_64_bytes 42501482 (+0%) 43009450 (+1%) 
6_blocksz_8192_bytes 50610176 (+0%) 50484565 (-0%) 
es_per_sec_ideal_min 20971520 (+0%) 20971520 (+0%) 
atform_AesThroughput       PASS (x)       PASS (x) 
atform_AesThroughput       PASS (x)       PASS (x) 
Benchmark Summary Table: AesThroughput
   Benchmark Summary          0 (0)          1 (1) 
6_blocksz_1024_bytes 49592320 (+0%) 49684138 (+0%) 
256_blocksz_16_bytes 28907317 (+0%) 29669280 (+3%) 
56_blocksz_256_bytes 48225450 (+0%) 48199168 (-0%) 
256_blocksz_64_bytes 42501482 (+0%) 43009450 (+1%) 
6_blocksz_8192_bytes 50610176 (+0%) 50484565 (-0%) 
es_per_sec_ideal_min 20971520 (+0%) 20971520 (+0%) 
atform_AesThroughput   ALL_PASS (x)   ALL_PASS (x) 
atform_AesThroughput   ALL_PASS (x)   ALL_PASS (x)


You get two tables in the output. The first table shows all the runs and the
second table averages the runs per image across iterations. In this case, since
the iteration count was 1, you get identical tables for "Benchmark" and
"Benchmark Summary". Above the tables is information about the images that were
used for the runs. The image information contains the image path as well as the
build time and the board.

For benchmarks with multiple fields within them that do not get averaged (example:
BootPerfServer's seconds_kernel_to_login{0,1,...}, cros_run_benchmarks.py
automatically averages them and displays them as <field_name>[c]. The average
used is arithmetic mean.


=== Scratch Cache ===

By default cros_run_benchmarks will cache the output of runs so it doesn't run
it again when you compare the same image with another one.

For example, you can set --images=A,B and it will run benchmarks with image A
and B. If you now set --images=A,C it will run benchmarks only on C and use the
cached results for image A.

To prevent it from using cached results rm the cros_scratch directory which
is created inside cros_scripts when cros_run_benchmarks runs.

The cache is also useful when you interrupt runs for some reason -- it will
continue from the same spot again.


=== How to get the script help message ===

If you've forgotten the switches this script has a help message that can be
obtained by invoking the script like this:

python cros_scripts/cros_run_benchmarks.py --help

Warning: Logs directory '/home/asharif/www/cros_scripts/logs/' already exists.
OUTPUT: cros_scripts/cros_run_benchmarks.py --help
Usage: cros_run_benchmarks.py [options]

Options:
  -h, --help            show this help message and exit
  -t TESTS, --tests=TESTS
                        Tests to compare.
  -c CHROMEOS_ROOT, --chromeos_root=CHROMEOS_ROOT
                        A *single* chromeos_root where scripts can be found.
  -i IMAGES, --images=IMAGES
                        Possibly multiple (comma-separated) chromeos images.
  -n ITERATIONS, --iterations=ITERATIONS
                        Iterations to run per benchmark.
  -r REMOTE, --remote=REMOTE
                        The remote chromeos machine.
  -b BOARD, --board=BOARD
                        The remote board.

"""

# Script to test the compiler.
import copy
import getpass
import optparse
import os
import sys
from utils import command_executer
from utils import utils
from utils import logger
import tempfile
import re
import subprocess
import multiprocessing
import math
import numpy
import hashlib
import image_chromeos
import pickle


def IsFloat(text):
  if text is None:
    return False
  try:
    float(text)
    return True
  except ValueError:
    return False


def RemoveTrailingZeros(x):
  ret = x
  ret = re.sub("\.0*$", "", ret)
  ret = re.sub("(\.[1-9]*)0+$", "\\1", ret)
  return ret


def HumanizeFloat(x, n=2):
  if not IsFloat(x):
    return x
  digits = re.findall("[0-9.]", str(x))
  decimal_found = False
  ret = ""
  sig_figs = 0
  for digit in digits:
    if digit == ".":
      decimal_found = True
    elif sig_figs !=0 or digit != "0":
      sig_figs += 1
    if decimal_found and sig_figs >= n:
      break
    ret += digit
  return ret


def GetNSigFigs(x, n=2):
  if not IsFloat(x):
    return x
  my_fmt = "%." + str(n-1) + "e"
  x_string = my_fmt % x
  f = float(x_string)
  return f


def GetFormattedPercent(baseline, other, bad_result="--"):
  result = "%8s" % GetPercent(baseline, other, bad_result)
  return result

def GetPercent(baseline, other, bad_result="--"):
  result = bad_result
  if IsFloat(baseline) and IsFloat(other):
    try:
      pct = (float(other)/float(baseline) - 1) * 100
      result = "%+1.1f" % pct
    except (ZeroDivisionError):
      pass
  return result

def FitString(text, N):
  if len(text) == N:
    return text
  elif len(text) > N:
    return text[-N:]
  else:
    fmt = "%%%ds" % N
    return fmt % text


class AutotestRun:
  def __init__(self, test, chromeos_root="", chromeos_image="",
               remote="", iteration=0, image_checksum=""):
    self.test = test
    self.chromeos_root = chromeos_root
    self.chromeos_image = chromeos_image
    self.remote = remote
    self.iteration = iteration
    self.output = ""
    self.results = {}
    l = logger.GetLogger()
    l.LogFatalIf(not image_checksum, "Checksum shouldn't be None")
    self.image_checksum = image_checksum


  def GetCacheHash(self):
    ret = "%s %s %s %d" % (self.image_checksum, self.test, self.remote, self.iteration)
    ret = re.sub("/", "__", ret)
    ret = re.sub(" ", "_", ret)
    return ret


  def GetLabel(self):
    ret = "%s %s %s" % (self.chromeos_image, self.test, self.remote)
    return ret


class TableFormatter:
  def __init__(self):
    self.d = "\t"
    self.bad_result = "x"
    pass


  def GetTablePercents(self, table):
    # Assumes table is not transposed.
    pct_table = []

    pct_table.append(table[0])
    for i in range(1, len(table)):
      row = []
      row.append(table[i][0])
      for j in range (1, len(table[0])):
        c = table[i][j]
        b = table[i][1]
        p = GetPercent(b, c, self.bad_result)
        row.append(p)
      pct_table.append(row)
    return pct_table


  def FormatFloat(self, c, max_length=8):
    if not IsFloat(c):
      return c
    f = float(c)
    ret = HumanizeFloat(f, 4)
    ret = RemoveTrailingZeros(ret)
    if len(ret) > max_length:
      ret = "%1.1ef" % f
    return ret


  def TransposeTable(self, table):
    transposed_table = []
    for i in range(len(table[0])):
      row = []
      for j in range(len(table)):
        row.append(table[j][i])
      transposed_table.append(row)
    return transposed_table


  def GetTableLabels(self, table):
    ret = ""
    header = table[0]
    for i in range(1, len(header)):
      ret += "%d: %s\n" % (i, header[i])
    return ret


  def GetFormattedTable(self, table, transposed=False,
                        first_column_width=30, column_width=14,
                        percents_only=True,
                        fit_string=True):
    o = ""
    pct_table = self.GetTablePercents(table)
    if transposed == True:
      table = self.TransposeTable(table)
      pct_table = self.TransposeTable(table)

    for i in range(0, len(table)):
      for j in range(len(table[0])):
        if j == 0:
          width = first_column_width
        else:
          width = column_width

        c = table[i][j]
        p = pct_table[i][j]

        # Replace labels with numbers: 0... n
        if IsFloat(c):
          c = self.FormatFloat(c)

        if IsFloat(p) and not percents_only:
          p = "%s%%" % p

        # Print percent values side by side.
        if j != 0:
          if percents_only:
            c = "%s" % p
          else:
            c = "%s (%s)" % (c, p)

        if i == 0 and j != 0:
          c = str(j)

        if fit_string:
          o += FitString(c, width) + self.d
        else:
          o += c + self.d
      o += "\n"
    return o


  def GetGroups(self, table):
    labels = table[0]
    groups = []
    group_dict = {}
    for i in range(1, len(labels)):
      label = labels[i]
      stripped_label = self.GetStrippedLabel(label)
      if stripped_label not in group_dict:
        group_dict[stripped_label] = len(groups)
        groups.append([])
      groups[group_dict[stripped_label]].append(i)
    return groups


  def GetSummaryTableValues(self, table):
    # First get the groups
    groups = self.GetGroups(table)

    summary_table = []

    labels = table[0]

    summary_labels = ["Summary Table"]
    for group in groups:
      label = labels[group[0]]
      stripped_label = self.GetStrippedLabel(label)
      group_label = "%s (%d runs)" % (stripped_label, len(group))
      summary_labels.append(group_label)
    summary_table.append(summary_labels)

    for i in range(1, len(table)):
      row = table[i]
      summary_row = [row[0]]
      for group in groups:
        group_runs = []
        for index in group:
          group_runs.append(row[index])
        group_run = self.AggregateResults(group_runs)
        summary_row.append(group_run)
      summary_table.append(summary_row)

    return summary_table


  # Drop N% slowest and M% fastest numbers, and return arithmean of
  # the remaining.
  @staticmethod
  def AverageWithDrops(numbers, slow_percent=20, fast_percent=20):
    sorted_numbers = list(numbers)
    sorted_numbers.sort()
    num_slow = int(slow_percent/100.0 * len(sorted_numbers))
    num_fast = int(fast_percent/100.0 * len(sorted_numbers))
    sorted_numbers = sorted_numbers[num_slow:]
    if num_fast:
      sorted_numbers = sorted_numbers[:-num_fast]
    return numpy.average(sorted_numbers)



  @staticmethod
  def AggregateResults(group_results):
    ret = ""
    if len(group_results) == 0:
      return ret
    all_floats = True
    all_passes = True
    all_fails = True
    for group_result in group_results:
      if not IsFloat(group_result):
        all_floats = False
      if group_result != "PASS":
        all_passes = False
      if group_result != "FAIL":
        all_fails = False
    if all_floats == True:
      float_results = [float(v) for v in group_results]
      ret = "%f" % TableFormatter.AverageWithDrops(float_results)
      # Add this line for standard deviation.
###      ret += " %f" % numpy.std(float_results)
    elif all_passes == True:
      ret = "ALL_PASS"
    elif all_fails == True:
      ret = "ALL_FAILS"
    return ret


  @staticmethod
  def GetStrippedLabel(label):
    return re.sub("\s*i:\d+$", "", label)


  @staticmethod
  def GetLabelWithIteration(label, iteration):
    return "%s i:%d" % (label, iteration)


class AutotestGatherer(TableFormatter):
  def __init__(self):
    self.runs = []
    TableFormatter.__init__(self)
    pass


  @staticmethod
  def MeanExcludingSlowest(array):
    mean = sum(array) / len(array)
    array2 = []

    for v in array:
      if mean != 0 and abs(v - mean)/mean < 0.2:
        array2.append(v)

    if len(array2) != 0:
      return sum(array2) / len(array2)
    else:
      return mean

  
  @staticmethod
  def AddComposite(results_dict):
    composite_keys = []
    composite_dict = {}
    for key in results_dict:
      mo = re.match("(.*){\d+}", key)
      if mo:
        composite_keys.append(mo.group(1))
    for key in results_dict:
      for composite_key in composite_keys:
        if key.count(composite_key) != 0 and IsFloat(results_dict[key]):
          if composite_key not in composite_dict:
            composite_dict[composite_key] = []
          composite_dict[composite_key].append(float(results_dict[key]))
          break

    for composite_key in composite_dict:
      v = composite_dict[composite_key]
      results_dict["%s[c]" % composite_key] = sum(v) / len(v)
      mean_excluding_slowest = AutotestGatherer.MeanExcludingSlowest(v)
      results_dict["%s[ce]" % composite_key] = mean_excluding_slowest

    return results_dict


  def ParseOutput(self, test):
    p=re.compile("^-+.*?^-+", re.DOTALL|re.MULTILINE)
    matches = p.findall(test.output)
    for i in range(len(matches)):
      results = matches[i]
      keyvals = results.split()[1:-1]
      results_dict = {}
      for j in range(len(keyvals)/2):
        # Eanble this to compare only numerical results.
###        if IsFloat(keyvals[j*2+1]):
        results_dict[keyvals[j*2]] = keyvals[j*2+1]

      # Add a composite keyval for tests like startup.
      results_dict = AutotestGatherer.AddComposite(results_dict)

      test.results = results_dict

      self.runs.append(test)

      # This causes it to not parse the table again
      # Autotest recently added a secondary table
      # That reports errors and screws up the final pretty output.
      break


  def GetFormattedMainTable(self, percents_only, fit_string):
    ret = ""
    table = self.GetTableValues()
    ret += self.GetTableLabels(table)
    ret += self.GetFormattedTable(table, percents_only=percents_only,
                                  fit_string=fit_string)
    return ret


  def GetFormattedSummaryTable(self, percents_only, fit_string):
    ret = ""
    table = self.GetTableValues()
    summary_table = self.GetSummaryTableValues(table)
    ret += self.GetTableLabels(summary_table)
    ret += self.GetFormattedTable(summary_table, percents_only=percents_only,
                                  fit_string=fit_string)
    return ret


  def GetBenchmarksString(self):
    ret = "Benchmarks (in order):"
    ret = "\n".join(self.GetAllBenchmarks())
    return ret


  def GetAllBenchmarks(self):
    all_benchmarks = []
    for run in self.runs:
      for key in run.results.keys():
        if key not in all_benchmarks:
          all_benchmarks.append(key)
    all_benchmarks.sort()
    return all_benchmarks


  def GetTableValues(self):
    table = []
    row = []

    row.append("Benchmark")
    for i in range(len(self.runs)):
      run = self.runs[i]
      label = run.GetLabel()
      label = self.GetLabelWithIteration(label, run.iteration)
      row.append(label)
    table.append(row)

    all_benchmarks = self.GetAllBenchmarks()
    for benchmark in all_benchmarks:
      row = []
      row.append(benchmark)
      for run in self.runs:
        results = run.results
        if benchmark in results:
          row.append(results[benchmark])
        else:
          row.append("")
      table.append(row)

    return table


class AutotestRunner:
  def __init__(self, chromeos_root, test, board="x86-agz", image=None, ag=None):
    self.chromeos_root = os.path.expanduser(chromeos_root)
    self.board = board
    if image:
      self.image = image
    else:
      self.image = ("%s/src/build/images/%s/latest/chromiumos_image.bin" 
                    % (chromeos_root,
                       board))
    self.image = os.path.realpath(self.image)

    if os.path.isdir(self.image):
      old_image = self.image
      self.image = "%s/chromiumos_image.bin" % self.image
      m = "%s is a dir. Trying to use %s instead..." % (old_image, self.image)
      logger.GetLogger().LogOutput(m)
      
    if not os.path.isfile(self.image):
      m = "Image: %s (%s) not found!" % (image, self.image)
      logger.GetLogger().LogError(m)
      sys.exit(1)

    self.test = test
    self.ag = ag
    self.ce = command_executer.GetCommandExecuter()
    self.scratch_dir = "%s/cros_scratch" % os.path.dirname(os.path.realpath(__file__))
    if not os.path.isdir(self.scratch_dir):
      os.mkdir(self.scratch_dir)

  def RunTest(self, remote, iterations):
    image_args = [os.path.dirname(os.path.abspath(__file__)) +
                    "/image_chromeos.py",
                    "--chromeos_root=" + self.chromeos_root,
                    "--image=" + self.image,
                    "--remote=" + remote,
                   ]
    if self.board:
      image_args.append("--board=" + self.board)

    image_checksum = utils.Md5File(self.image)

    reimaged = False
 
    for i in range(iterations):
      options = ""
      if self.board:
        options += "--board=%s" % self.board

      run = AutotestRun(self.test, self.chromeos_root,
                        self.image, remote, i, image_checksum)
      cache_file = run.GetCacheHash()
      f = "%s/%s" % (self.scratch_dir, cache_file)
      if os.path.isfile(f):
        m = "Cache hit: %s. Not running test for image: %s.\n" % (f, self.image)
        logger.GetLogger().LogOutput(m)
        pickle_file = open(f, "rb")
        retval = pickle.load(pickle_file)
        out = pickle.load(pickle_file)
        err = pickle.load(pickle_file)
        pickle_file.close()
        logger.GetLogger().LogOutput(out)
      else:
        if reimaged == False:
          retval = image_chromeos.Main(image_args)
          logger.GetLogger().LogFatalIf(retval, "Could not re-image!")
          reimaged = True
        command = "cd %s/src/scripts" % self.chromeos_root
        command += ("&& ./enter_chroot.sh -- ./run_remote_tests.sh --remote=%s %s %s" %
                    (remote,
                     options,
                     self.test))
        [retval, out, err] = self.ce.RunCommand(command, True)
        pickle_file = open(f, "wb")
        pickle.dump(retval, pickle_file)
        pickle.dump(out, pickle_file)
        pickle.dump(err, pickle_file)
        pickle_file.close()

      run.output = out
      self.ag.ParseOutput(run)


def CanonicalizeChromeOSRoot(chromeos_root):
  chromeos_root = os.path.expanduser(chromeos_root)
  if os.path.isfile(os.path.join(chromeos_root,
                                 "src/scripts/enter_chroot.sh")):
    return chromeos_root
  else:
    return None


class Benchmark:
  def __init__(self, name, iterations, args=None):
    self.name = name
    self.iterations = iterations
    self.args = args


def Main(argv):
  """The main function."""
  # Common initializations
###  command_executer.InitCommandExecuter(True)
  ce = command_executer.GetCommandExecuter()
  l = logger.GetLogger()

  parser = optparse.OptionParser()
  parser.add_option("-t", "--tests", dest="tests",
                    help=("Tests to compare."
                          "Optionally specify per-test iterations by <test>:<iter>"))
  parser.add_option("-c", "--chromeos_root", dest="chromeos_root",
                    help="A *single* chromeos_root where scripts can be found.")
  parser.add_option("-i", "--images", dest="images",
                    help="Possibly multiple (comma-separated) chromeos images.")
  parser.add_option("-n", "--iterations", dest="iterations",
                    help="Iterations to run per benchmark.",
                    default=1)
  parser.add_option("-r", "--remote", dest="remote",
                    help="The remote chromeos machine.")
  parser.add_option("-b", "--board", dest="board",
                    help="The remote board.",
                    default="x86-mario")
  parser.add_option("--full_table", dest="full_table",
                    help="Print full tables.",
                    action="store_true",
                    default=False)
  parser.add_option("--fit_string", dest="fit_string",
                    help="Fit strings to fixed sizes.",
                    action="store_true",
                    default=False)
  parser.add_option("--image_chromeos_root",
                    dest="image_chromeos_root",
                    help="Use the chromeos_root of the image, when available.",
                    action="store_true",
                    default=False)
  l.LogOutput(" ".join(argv))
  [options, args] = parser.parse_args(argv)

  if options.remote is None:
    l.LogError("No remote machine specified.")
    parser.print_help()
    sys.exit(1)

  remote = options.remote

  benchmarks = []

  if options.tests:
    benchmark_strings = options.tests.split(",")
    for benchmark_string in benchmark_strings:
      iterations = int(options.iterations)
      fields = benchmark_string.split(":")
      l.LogFatalIf(len(fields)>2,
                   "Benchmark string: %s flawed" % benchmark_string)
      name = fields[0]
      if len(fields) == 2:
        iterations = int(fields[1])
      benchmarks.append(Benchmark(name, iterations))
  else:
    iterations = int(options.iterations)
###    benchmarks.append(Benchmark("BootPerfServer/control", iterations))
###    benchmarks.append(Benchmark("Page --args=\"--page-cycler-gtest-filters=PageCyclerTest.BloatFile\"", iterations))
    benchmarks.append(Benchmark("Page", iterations))
###    benchmarks.append(Benchmark("bvt", iterations))
###    benchmarks.append(Benchmark("suite_Smoke", iterations))
###    benchmarks.append(Benchmark("SunSpider", iterations))
###    benchmarks.append(Benchmark("V8Bench", iterations))
###    benchmarks.append(Benchmark("graphics_GLBench", iterations))
###    benchmarks.append(Benchmark("unixbench", iterations))
###    benchmarks.append(Benchmark("compilebench", iterations))
###    benchmarks.append(Benchmark("audiovideo_FFMPEG", iterations))
###    benchmarks.append(Benchmark("audiovideo_V4L2", iterations))
###    benchmarks.append(Benchmark("hackbench", iterations))
###    benchmarks.append(Benchmark("dbench", iterations))


  main_chromeos_root = options.chromeos_root
  if main_chromeos_root:
    main_chromeos_root = CanonicalizeChromeOSRoot(main_chromeos_root)
    if not main_chromeos_root:
      message = "chromeos_root: %s not valid." % options.chromeos_root
      l.LogError(message)
      sys.exit(1)
  else:
    message = "Using image-derived chromeos_root."
    l.LogOutput(message)

  if not options.images:
    l.LogError("No images specified.")
    parser.print_help()
    sys.exit(1)

  ags = {}
  try:
    # Lock the machine if it is of this style: chromeos-test\d+
    match = re.search("chromeos-test(\d+)$", remote)
    if match:
      index = match.group(1)
      perflab_machine = "chromeos_%s_%s" % (options.board, index)
      lock_reason = ("Automatically locked by %s@%s for testing new toolchain using %s" %
                     (getpass.getuser(),
                      os.uname()[1],
                      sys.argv[0]))
      lock_reason = "Automatically locked by %s" % os.path.basename(sys.argv[0])
      command = ("perflab --machines=%s --lock_reason=%r --lock_duration=1d lock" %
                 (perflab_machine, lock_reason))
      retval = ce.RunCommand(command)
      l.LogFatalIf(retval, "Could not lock machine %s through perflab" % perflab_machine)

    for image in options.images.split(","):
      if image == "":
        l.LogWarning("Empty image specified!")
        continue
      image = os.path.expanduser(image)
      for b in benchmarks:
        if b in ags:
          ag = ags[b]
        else:
          ag = AutotestGatherer()
          ags[b] = ag

        image_chromeos_root = os.path.join(os.path.dirname(image),
                                           "../../../../..")
        image_chromeos_root = CanonicalizeChromeOSRoot(image_chromeos_root)

        chromeos_root = main_chromeos_root

        if options.image_chromeos_root:
          l.LogFatalIf(not image_chromeos_root,
                       "image chromeos_root not valid.")
          m = "Using image chromeos root: %s" % image_chromeos_root
          chromeos_root = image_chromeos_root
          l.LogOutput(m)

        ar = AutotestRunner(chromeos_root, b.name, options.board, image=image, ag=ag)
        ar.RunTest(remote, b.iterations)

    output = ""
    for b, ag in ags.items():
      output += "Benchmark: %s\n" % b.name
      output += ag.GetFormattedMainTable(percents_only=not options.full_table,
                                         fit_string=options.fit_string)
      output += "\n"
      output += "Benchmark Summary Table: %s\n" % b.name
      output += ag.GetFormattedSummaryTable(percents_only=not options.full_table,
                                            fit_string=options.fit_string)
      output += "\n"
    l.LogOutput(output)


  except (KeyboardInterrupt, SystemExit):
    print "C-c pressed"
  if match:
    command = ("perflab --machines=%s --lock_reason=%r unlock" %
               (perflab_machine, lock_reason))
    retval = ce.RunCommand(command)


if __name__ == "__main__":
  Main(sys.argv)

