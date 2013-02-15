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
                    default="latest",
                    help=("Use these chromeos versions." +
                          "Example: -c latest,weekly,quarterly")
                    )
  parser.add_option("-t",
                    "--toolchain",
                    dest="toolchain",
                    default="trunk",
                    help="Toolchain to use {trunk|branch|custom}"
                    )
  parser.add_option("-p",
                    "--p4-snapshot",
                    default="",
                    help="An existing perforce checkout for debugging."
                    )
  options = parser.parse_args(argv)[0]

  server = xmlrpclib.Server("http://localhost:8000")

  all_jobs = []
  tc_job = jobs_helper.CreateBuildTCJob(p4_snapshot=options.p4_snapshot)
  all_jobs.append(tc_job)

  versions = options.chromeos_versions
  versions = versions.strip()

  for version in versions.split(","):
    build_chromeos_job = (
        jobs_helper.CreateBuildAndTestChromeOSJob(
          tc_job,
          version,
          p4_snapshot=options.p4_snapshot))
    all_jobs.append(build_chromeos_job)

  group = job_group.JobGroup(os.uname()[1], "/tmp/", all_jobs, False, False)
  server.ExecuteJobGroup(utils.Serialize(group))

if __name__ == "__main__":
  Main(sys.argv)
