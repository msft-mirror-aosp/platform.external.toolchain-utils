#!/usr/bin/python
#
# Copyright 2011 Google Inc. All Rights Reserved.

import getpass
import glob
import hashlib
import os
import pickle
import re
import tempfile

from image_checksummer import ImageChecksummer
from utils import command_executer
from utils import logger
from utils import misc


SCRATCH_DIR = "/home/%s/cros_scratch" % getpass.getuser()
RESULTS_FILE = "results.txt"
AUTOTEST_TARBALL = "autotest.tbz2"
PERF_RESULTS_FILE = "perf-results.txt"


class Result(object):
  """ This class manages what exactly is stored inside the cache without knowing
  what the key of the cache is. For runs with perf, it stores perf.data,
  perf.report, etc. The key generation is handled by the ResultsCache class.
  """
  def __init__(self, chromeos_root, logger):
    self._chromeos_root = chromeos_root
    self._logger = logger
    self._ce = command_executer.GetCommandExecuter(self._logger)
    self._temp_dir = None

  def _CopyFilesTo(self, dest_dir, files_to_copy):
    file_index = 0
    for file_to_copy in files_to_copy:
      if not os.path.isdir(dest_dir):
        command = "mkdir -p %s" % dest_dir
        self._ce.RunCommand(command)
      dest_file = os.path.join(dest_dir,
                               ("%s.%s" % (os.path.basename(file_to_copy),
                                           file_index)))
      ret = self._ce.CopyFiles(file_to_copy,
                               dest_file,
                               recursive=False)
      if ret:
        raise Exception("Could not copy results file: %s" % file_to_copy)

  def CopyResultsTo(self, dest_dir):
    self._CopyFilesTo(dest_dir, self.perf_data_files)
    self._CopyFilesTo(dest_dir, self.perf_report_files)

  def _GetKeyvals(self):
    generate_test_report = os.path.join(self._chromeos_root,
                                        "src",
                                        "platform",
                                        "crostestutils",
                                        "utils_py",
                                        "generate_test_report.py")
    command = ("python %s --no-color --csv %s" %
               (generate_test_report,
                self.results_dir))
    [ret, out, err] = self._ce.RunCommand(command, return_output=True)
    keyvals_dict = {}
    for line in out.splitlines():
      tokens = line.split(",")
      key = tokens[-2]
      if key.startswith(self.results_dir):
        key = key[len(self.results_dir) + 1:]
      value = tokens[-1]
      keyvals_dict[key] = value

    return keyvals_dict

  def _GetResultsDir(self):
    mo = re.search("Results placed in (\S+)", self.out)
    if mo:
      result = mo.group(1)
      return result
    raise Exception("Could not find results directory.")

  def _FindFilesInResultsDir(self, find_args):
    command = "find %s %s" % (self.results_dir,
                              find_args)
    ret, out, err = self._ce.RunCommand(command, return_output=True)
    if ret:
      raise Exception("Could not run find command!")
    return out

  def _GetPerfDataFiles(self):
    return self._FindFilesInResultsDir("-name perf.data").splitlines()

  def _GetPerfReportFiles(self):
    return self._FindFilesInResultsDir("-name perf.data.report").splitlines()

  def _GeneratePerfReportFiles(self):
    perf_report_files = []
    for perf_data_file in self.perf_data_files:
      # Generate a perf.report and store it side-by-side with the perf.data
      # file.
      chroot_perf_data_file = misc.GetInsideChrootPath(self._chromeos_root,
                                                       perf_data_file)
      perf_report_file = "%s.report" % perf_data_file
      if os.path.exists(perf_report_file):
        raise Exception("Perf report file already exists: %s" %
                        perf_report_file)
      chroot_perf_report_file = misc.GetInsideChrootPath(self._chromeos_root,
                                                   perf_report_file)
      command = ("/usr/sbin/perf report "
                 "-n "
                 "--symfs /build/%s "
                 "--vmlinux /build/%s/usr/lib/debug/boot/vmlinux "
                 "--kallsyms /build/%s/boot/System.map-* "
                 "-i %s --stdio "
                 "| head -n1000 "
                 "| tee %s" %
                 (self._board,
                  self._board,
                  self._board,
                  chroot_perf_data_file,
                  chroot_perf_report_file))
      ret, out, err = self._ce.ChrootRunCommand(self._chromeos_root,
                                                command,
                                                return_output=True)
      # Add a keyval to the dictionary for the events captured.
      perf_report_files.append(
          misc.GetOutsideChrootPath(self._chromeos_root,
                                    chroot_perf_report_file))
    return perf_report_files

  def _GatherPerfResults(self):
    report_id = 0
    for perf_report_file in self.perf_report_files:
      with open(perf_report_file, "r") as f:
        report_contents = f.read()
        for group in re.findall("Events: (\S+) (\S+)", report_contents):
          num_events = group[0]
          event_name = group[1]
          key = "perf_%s_%s" % (report_id, event_name)
          value = str(misc.UnitToNumber(num_events))
          self.keyvals[key] = value

  def _PopulateFromRun(self, board, out, err, retval):
    self._board = board
    self.out = out
    self.err = err
    self.retval = retval
    self.chroot_results_dir = self._GetResultsDir()
    self.results_dir = misc.GetOutsideChrootPath(self._chromeos_root,
                                                 self.chroot_results_dir)
    self.perf_data_files = self._GetPerfDataFiles()
    # Include all perf.report data in table.
    self.perf_report_files = self._GeneratePerfReportFiles()
    # TODO(asharif): Do something similar with perf stat.

    # Grab keyvals from the directory.
    self._ProcessResults()

  def _ProcessResults(self):
    # Note that this function doesn't know anything about whether there is a
    # cache hit or miss. It should process results agnostic of the cache hit
    # state.
    self.keyvals = self._GetKeyvals()
    self.keyvals["retval"] = self.retval
    # Generate report from all perf.data files.
    # Now parse all perf report files and include them in keyvals.
    self._GatherPerfResults()

  def _PopulateFromCacheDir(self, cache_dir):
    # Read in everything from the cache directory.
    with open(os.path.join(cache_dir, RESULTS_FILE), "r") as f:
      self.out = pickle.load(f)
      self.err = pickle.load(f)
      self.retval = pickle.load(f)

    # Untar the tarball to a temporary directory
    self._temp_dir = tempfile.mkdtemp()
    command = ("cd %s && tar xf %s" %
               (self._temp_dir,
                os.path.join(cache_dir, AUTOTEST_TARBALL)))
    ret = self._ce.RunCommand(command)
    if ret:
      raise Exception("Could not untar cached tarball")
    self.results_dir = self._temp_dir
    self.perf_data_files = self._GetPerfDataFiles()
    self.perf_report_files = self._GetPerfReportFiles()
    self._ProcessResults()

  def CleanUp(self):
    if self._temp_dir:
      command = "rm -rf %s" % self._temp_dir
      self._ce.RunCommand(command)


  def StoreToCacheDir(self, cache_dir):
    # Create the dir if it doesn't exist.
    command = "mkdir -p %s" % cache_dir
    ret = self._ce.RunCommand(command)
    if ret:
      raise Exception("Could not create cache dir: %s" % cache_dir)
    # Store to the cache directory.
    with open(os.path.join(cache_dir, RESULTS_FILE), "w") as f:
      pickle.dump(self.out, f)
      pickle.dump(self.err, f)
      pickle.dump(self.retval, f)

    tarball = os.path.join(cache_dir, AUTOTEST_TARBALL)
    command = ("cd %s && tar cjf %s ." % (self.results_dir, tarball))
    ret = self._ce.RunCommand(command)
    if ret:
      raise Exception("Couldn't store autotest output directory.")

  @classmethod
  def CreateFromRun(cls, logger, chromeos_root, board, out, err, retval):
    result = cls(chromeos_root, logger)
    result._PopulateFromRun(board, out, err, retval)
    return result

  @classmethod
  def CreateFromCacheHit(cls, chromeos_root, logger, cache_dir):
    result = cls(chromeos_root, logger)
    try:
      result._PopulateFromCacheDir(cache_dir)
    except Exception as e:
      logger.LogError("Exception while using cache: %s" % e)
      return None
    return result


class CacheConditions(object):
  # Cache hit only if the result file exists.
  CACHE_FILE_EXISTS = 0

  # Cache hit if the ip address of the cached result and the new run match.
  REMOTES_MATCH = 1

  # Cache hit if the image checksum of the cached result and the new run match.
  CHECKSUMS_MATCH = 2

  # Cache hit only if the cached result was successful
  RUN_SUCCEEDED = 3

  # Never a cache hit.
  FALSE = 4

  # Cache hit if the image path matches the cached image path.
  IMAGE_PATH_MATCH = 5


class ResultsCache(object):
  """ This class manages the key of the cached runs without worrying about what
  is exactly stored (value). The value generation is handled by the Results
  class.
  """
  CACHE_VERSION = 4
  def Init(self, chromeos_image, chromeos_root, autotest_name, iteration,
           autotest_args, remote, board, cache_conditions,
           logger_to_use):
    self.chromeos_image = chromeos_image
    self.chromeos_root = chromeos_root
    self.autotest_name = autotest_name
    self.iteration = iteration
    self.autotest_args = autotest_args,
    self.remote = remote
    self.board = board
    self.cache_conditions = cache_conditions
    self._logger = logger_to_use
    self._ce = command_executer.GetCommandExecuter(self._logger)

  def _GetCacheDirForRead(self):
    glob_path = self._FormCacheDir(self._GetCacheKeyList(True))
    matching_dirs = glob.glob(glob_path)

    if matching_dirs:
      # Cache file found.
      if len(matching_dirs) > 1:
        self._logger.LogError("Multiple compatible cache files: %s." %
                              " ".join(matching_dirs))
      return matching_dirs[0]
    else:
      return None

  def _GetCacheDirForWrite(self):
    return self._FormCacheDir(self._GetCacheKeyList(False))

  def _FormCacheDir(self, list_of_strings):
    cache_key = " ".join(list_of_strings)
    cache_dir = misc.GetFilenameFromString(cache_key)
    cache_path = os.path.join(SCRATCH_DIR, cache_dir)
    return cache_path

  def _GetCacheKeyList(self, read):
    if read and CacheConditions.REMOTES_MATCH not in self.cache_conditions:
      remote = "*"
    else:
      remote = self.remote
    if read and CacheConditions.CHECKSUMS_MATCH not in self.cache_conditions:
      checksum = "*"
    else:
      checksum = ImageChecksummer().Checksum(self.chromeos_image)

    if read and CacheConditions.IMAGE_PATH_MATCH not in self.cache_conditions:
      image_path_checksum = "*"
    else:
      image_path_checksum = hashlib.md5(self.chromeos_image).hexdigest()

    autotest_args_checksum = hashlib.md5(
                             "".join(self.autotest_args)).hexdigest()

    return (image_path_checksum,
            self.autotest_name, str(self.iteration),
            autotest_args_checksum,
            checksum,
            remote,
            str(self.CACHE_VERSION))

  def ReadResult(self):
    if CacheConditions.FALSE in self.cache_conditions:
      return None
    cache_dir = self._GetCacheDirForRead()

    if not cache_dir:
      return None

    if not os.path.isdir(cache_dir):
      return None

    self._logger.LogOutput("Trying to read from cache dir: %s" % cache_dir)

    result = Result.CreateFromCacheHit(self.chromeos_root,
                                       self._logger, cache_dir)

    if not result:
      return None

    if (result.retval == 0 or
        CacheConditions.RUN_SUCCEEDED not in self.cache_conditions):
      return result

    return None

  def StoreResult(self, result):
    cache_dir = self._GetCacheDirForWrite()
    result.StoreToCacheDir(cache_dir)


class MockResultsCache(object):
  def Init(self, *args):
    pass

  def ReadResult(self):
    return Result("Results placed in /tmp/test", "", 0)

  def StoreResult(self, result):
    pass
