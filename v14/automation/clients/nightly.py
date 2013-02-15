import sys
from utils import utils
import xmlrpclib
from automation.common import job
from automation.common import job_group
import jobs_helper
import optparse
import os


def Main(argv):
  """The main function."""
  parser = optparse.OptionParser()
  parser.add_option("-t",
                    "--toolchain",
                    dest="toolchain",
                    default="v2",
                    help="Toolchain to use {trunk|branch}"
                    )
  parser.add_option("-b",
                    "--board",
                    dest="board",
                    default="x86-agz",
                    help="Board to use for the nightly job."
                    )
  parser.add_option("-l",
                    "--perflab-benchmarks",
                    dest="perflab_benchmarks",
                    default="chromeos/cpu/bikjmp" +
                    ",chromeos/browser/sunspider" +
                    ",chromeos/browser/pagecycler",
                    help="Comma-separated perflab benchmarks to run")
  options = parser.parse_args(argv)[0]

  server = xmlrpclib.Server("http://localhost:8000")

  all_jobs = []
  tc_job = jobs_helper.CreateBuildTCJob(toolchain=options.toolchain,
                                        board=options.board)
  all_jobs.append(tc_job)

  tc_root = jobs_helper.GetTCRootDir(options.toolchain)[1]

  # Perform the correctness tests
  build_chromeos_job = jobs_helper.CreateBuildAndTestChromeOSJob(
      "weekly",
      toolchain=options.toolchain,
      board=options.board)
  build_chromeos_job.AddRequiredFolder(tc_job,
      tc_root + jobs_helper.tc_pkgs_dir,
      tc_root + jobs_helper.tc_pkgs_dir)
  all_jobs.append(build_chromeos_job)

  dejagnu_job = jobs_helper.CreateDejaGNUJob(
      toolchain=options.toolchain,
      board=options.board)
  dejagnu_job.AddRequiredFolder(tc_job,
      tc_root + jobs_helper.tc_pkgs_dir,
      tc_root + jobs_helper.tc_pkgs_dir)
  dejagnu_job.AddRequiredFolder(tc_job,
      tc_root + jobs_helper.tc_objects_dir,
      tc_root + jobs_helper.tc_objects_dir)

  all_jobs.append(dejagnu_job)

  # Perform the performance tests
  perflab_job = jobs_helper.CreatePerflabJob(
      "quarterly",
      options.perflab_benchmarks,
      toolchain=options.toolchain,
      board=options.board)
  perflab_job.AddRequiredFolder(tc_job,
      tc_root + jobs_helper.tc_pkgs_dir,
      tc_root + jobs_helper.tc_pkgs_dir)
  all_jobs.append(perflab_job)

  group = job_group.JobGroup("nightly_client", all_jobs, False, False)
  server.ExecuteJobGroup(utils.Serialize(group))

if __name__ == "__main__":
  Main(sys.argv)
