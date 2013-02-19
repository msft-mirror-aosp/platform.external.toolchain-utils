# Copyright 2012 Google Inc. All Rights Reserved.
#!/usr/bin/python2.6
"""A script that symbolizes perf.data files."""
import optparse
import os
import shutil
from subprocess import PIPE
from subprocess import Popen
from utils import misc


GSUTIL_CMD = "gsutil cp gs://chromeos-image-archive/%s-release/%s/debug.tgz %s"
TAR_CMD = "tar -zxvf %s -C %s"
PERF_BINARY = "/google/data/ro/projects/perf/perf"
VMLINUX_FLAG = " --vmlinux=/usr/lib/debug/usr/lib/debug/boot/vmlinux.debug"
PERF_CMD = PERF_BINARY +" report -i %s -n --symfs=%s" + VMLINUX_FLAG


def main():
  parser = optparse.OptionParser()
  parser.add_option("--in", dest="in_dir")
  parser.add_option("--out", dest="out_dir")
  parser.add_option("--cache", dest="cache")
  (opts, _) = parser.parse_args()
  if not _ValidateOpts(opts):
    return 1
  else:
    for filename in os.listdir(opts.in_dir):
      _DownloadSymbols(filename, opts.cache)
      _PerfReport(filename, opts.in_dir, opts.out_dir, opts.cache)
  return 0


def _ValidateOpts(opts):
  """Ensures all directories exist, before attempting to populate."""
  if not os.path.exists(opts.in_dir):
    print "Input directory doesn't exist."
    return False
  if not os.path.exists(opts.out_dir):
    print "Output directory doesn't exist."
    return False
  if not os.path.exists(opts.cache):
    print "Cache directory doesn't exist."
    return False
  return True


def _ParseFilename(filename, canonical=False):
  """Returns a tuple (database_key, board, lsb_version).
     If canonical is True, instead returns (database_key, board, canonical_vers)
     canonical_vers includes the revision string.
  """
  [key, board, vers] = filename.split("~")
  if canonical:
    vers = misc.GetChromeOSVersionFromLSBVersion(vers)
  return (key, board, vers)


def _DownloadSymbols(filename, cache):
  """ Incrementally downloads appropriate symbols.
      We store the downloads in cache, with each set of symbols in a TLD
      named like cache/$board-release~$canonical_vers/usr/lib/debug
  """
  _, board, vers = _ParseFilename(filename, canonical=True)
  symbol_cache_tld = "%s-release~%s" % (board, vers)
  download_path = os.path.join(cache, symbol_cache_tld, "usr/lib/")
  symbol_tgz_path = os.path.join(download_path, "debug.tgz")
  # First, check if the TLD exists already. If it does, then assume we've got
  # the appropriate symbols.
  if os.path.exists(download_path):
    print "Symbol directory exists, skipping download."
    return
  else:
    os.makedirs(download_path)
    download_cmd = GSUTIL_CMD % (board, vers, download_path)
    print "Downloading symbols for %s" % filename
    print download_cmd
    download_proc = Popen(download_cmd.split(), stdout=PIPE)
    out = download_proc.stdout.read()
    if "InvalidUriError" in out:
      print "Attempted to download non-existing symbols."
      # Clean up the empty directory structures.
      shutil.rmtree(os.path.join(cache, symbol_cache_tld))
      raise IOError
    # Otherwise, assume download proceeded as planned.
    extract_cmd = TAR_CMD % (symbol_tgz_path, download_path)
    print "Extracting symbols for %s" % filename
    print extract_cmd
    process = Popen(extract_cmd.split())
    # Wait for the unzipping to finish.
    process.wait()
    # Clean up the .tgz file.
    os.remove(symbol_tgz_path)


def _PerfReport(filename, in_dir, out_dir, cache):
  """ Call perf report on the file, storing output to the output dir.
      The output is currently stored as $out_dir/$key_report
  """
  key, board, vers = _ParseFilename(filename, canonical=True)
  symbol_cache_tld = "%s-release~%s" % (board, vers)
  input_file = os.path.join(in_dir, filename)
  symfs = os.path.join(cache, symbol_cache_tld)
  report_cmd = PERF_CMD % (input_file, symfs)
  print "Reporting."
  print report_cmd
  report_proc = Popen(report_cmd.split(), stdout=PIPE)
  outfile = open(os.path.join(out_dir, key+"_report"), "w")
  outfile.write(report_proc.stdout.read())
  outfile.close()


if __name__ == "__main__":
  exit(main())
