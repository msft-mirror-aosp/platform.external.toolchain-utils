import sys
from utils import utils
import xmlrpclib
from automation.common import job
from automation.common import job_group
from automation.common import jobs_helper
import optparse
import os


def Main(argv):
  """The main function."""
  parser = optparse.OptionParser()
  parser.add_option("-c",
                    "--chromeos-versions",
                    dest="chromeos_versions",
                    help=("Use these chromeos versions." +
                          "Example: -c latest,weekly,quarterly")
                    )
  parser.add_option("-t",
                    "--toolchain",
                    dest="toolchain",
                    default="v1",
                    help="Toolchain to use {trunk|v1}"
                    )
  parser.add_option("-b",
                    "--board",
                    dest="board",
                    default="x86-generic",
                    help="Board to build for."
                    )
  parser.add_option("-p",
                    "--p4-snapshot",
                    dest="p4_snapshot",
                    default="",
                    help="An existing perforce checkout for debugging."
                    )
  parser.add_option("-d",
                    "--deja-gnu",
                    dest="dejagnu",
                    default=False,
                    action="store_true",
                    help="Should the deja-gnu tests be run?")
  parser.add_option("-l",
                    "--perflab-benchmarks",
                    dest="perflab_benchmarks",
                    help="Comma-separated perflab benchmarks to run")
  options = parser.parse_args(argv)[0]

  server = xmlrpclib.Server("http://localhost:8000")

  all_jobs = []
  tc_job = jobs_helper.CreateBuildTCJob(p4_snapshot=options.p4_snapshot,
                                        toolchain=options.toolchain)
  tc_pkgs_dir = job.FolderDependency(tc_job, tc_root + jobs_helper.tc_pkgs_dir)
  tc_objects_dir = job.FolderDependency(tc_job,
                                        tc_root + jobs_helper.tc_objects_dir)
  all_jobs.append(tc_job)

  versions = ""

  if options.chromeos_versions:
    versions = options.chromeos_versions.strip()

  perflab_benchmarks = []

  if options.perflab_benchmarks:
    perflab_benchmarks += options.perflab_benchmarks.split(",")

  for version in versions.split(","):
    if not version:
      break

    tc_root = jobs_helper.GetTCRootDir(options.toolchain)[1]

    build_chromeos_job = \
        jobs_helper.CreateBuildAndTestChromeOSJob(version,
                                                  p4_snapshot=options.p4_snapshot,
                                                  toolchain=options.toolchain)
    build_chromeos_job.DependsOnFolder(tc_pkgs_dir)
    all_jobs.append(build_chromeos_job)

    for pb in perflab_benchmarks:
      perflab_job = jobs_helper.CreatePerflabJob(version, pb,
                                                 p4_snapshot=options.p4_snapshot,
                                                 toolchain=options.toolchain)
      perflab_job.DependsOnFolder(tc_pkgs_dir)
      all_jobs.append(perflab_job)

  if options.dejagnu:
    dejagnu_job = jobs_helper.CreateDejaGNUJob(p4_snapshot=options.p4_snapshot,
                                               toolchain=options.toolchain)
    tc_root = jobs_helper.GetTCRootDir(options.toolchain)[1]
    dejagnu_job.DependsOnFolder(tc_objects_dir)
    dejagnu_job.DependsOnFolder(tc_pkgs_dir)

    all_jobs.append(dejagnu_job)

  group = job_group.JobGroup("test_client", all_jobs, False, False)
  server.ExecuteJobGroup(utils.Serialize(group))

if __name__ == "__main__":
  Main(sys.argv)
