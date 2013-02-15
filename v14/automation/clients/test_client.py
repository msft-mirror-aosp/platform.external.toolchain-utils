import sys
from utils import utils
import xmlrpclib
from automation.common import job
from automation.common import jobs_helper
import optparse


def Main(argv):
  """The main function."""
  parser = optparse.OptionParser()
  parser.add_option("-w",
                    "--weekly",
                    dest="weekly",
                    action="store_true",
                    default=False,
                    help="Use weekly chromeos checkout."
                    )
  parser.add_option("-q",
                    "--quarterly",
                    dest="quarterly",
                    action="store_true",
                    default=False,
                    help="Use quarterly chromeos checkout."
                    )
  parser.add_option("-t",
                    "--toolchain",
                    dest="toolchain",
                    default="trunk",
                    help="Toolchain to use {trunk|branch|custom}"
                    )
  options = parser.parse_args(argv)[0]

  server = xmlrpclib.Server("http://localhost:8000")

  all_jobs = []
  tc_job = jobs_helper.CreateBuildTCJob()
  all_jobs.append(tc_job)

  build_chromeos_job = (
      jobs_helper.CreateBuildChromeOSJob(
        tc_job))
  all_jobs.append(build_chromeos_job)
###  run_test_job = jobs_helper.CreateTestJob(p4_job, "cros1")
###  all_jobs.append(run_test_job)

  server.ExecuteJobGroup(utils.Serialize(all_jobs))

if __name__ == "__main__":
  Main(sys.argv)
