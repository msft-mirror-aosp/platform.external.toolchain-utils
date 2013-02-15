import xmlrpclib
from utils import utils
from automation.common import job
from automation.common import jobs_helper

server = xmlrpclib.Server("http://localhost:8000")

all_jobs = []
tc_job = jobs_helper.CreateBuildTCJob()
all_jobs.append(tc_job)
build_chromeos_job = jobs_helper.CreateBuildChromeOSJob(tc_job)
all_jobs.append(build_chromeos_job)
###run_test_job = jobs_helper.CreateTestJob(p4_job, "cros1")
###all_jobs.append(run_test_job)

server.ExecuteJobGroup(utils.Serialize(all_jobs))

