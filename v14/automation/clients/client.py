import xmlrpclib
from utils import utils
from automation.common import job
from automation.common import job_group

server = xmlrpclib.Server("http://localhost:8000")

blah_job = job.Job("echo \"Installing autotest on\nMYTEST1 PASS\nMYTEST2 FAIL\" > log.txt")
blah_job.AddRequiredMachine("", "linux", False)
blah_job.AddLowLevelLog("log.txt")
blah_job2 = job.Job("mkdir blah; echo \"Installing autotest on\nMYTEST3 FAIL\nMYTEST4 PASS\" > blah/log.txt")
blah_job2.AddRequiredMachine("", "linux", False)
blah_job2.AddLowLevelLog("blah/log.txt")
#cat_job = job.Job("cat hello.txt")
#cat_job.AddRequiredMachine("", "linux", False)
#cat_job.AddRequiredFolder(blah_job, "blah.txt", "hello.txt", True)
#cat_job2 = job.Job("cat hello.txt")
#cat_job2.AddRequiredMachine("", "linux", False)
#cat_job2.AddRequiredFolder(cat_job, "hello.txt", "hello.txt", False)
#cat_job2.AddResultsDir("hello.txt")

yes_job = job.Job("yes")
yes_job.AddRequiredMachine("", "linux", False)

group = job_group.JobGroup([blah_job, blah_job2],
                           False, False, baseline_file_src="/tmp/baseline2.csv")

ids = server.ExecuteJobGroup(utils.Serialize(group), True)

