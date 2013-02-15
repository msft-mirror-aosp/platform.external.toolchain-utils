import getpass
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
                    "--chromeos-version",
                    dest="chromeos_version",
                    default="weekly",
                    help=("Update what version of chromeos.")
                    )
  options = parser.parse_args(argv)[0]

  server = xmlrpclib.Server("http://localhost:8000")

  all_jobs = []
  update_job = jobs_helper.CreateUpdateJob(options.chromeos_version)
  all_jobs.append(update_job)

  group = job_group.JobGroup(all_jobs, False, False)
  server.ExecuteJobGroup(utils.Serialize(group))

if __name__ == "__main__":
  Main(sys.argv)

