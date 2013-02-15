import xmlrpclib
from utils import utils
from automation.common import job
from automation.common import job_group

server = xmlrpclib.Server("http://localhost:8000")

blah_job = job.Job("""/usr/local/google/home/raymes/crosstool/chromeos-toolchain/gcctools/chromeos/v14/summarize_results.py /tmp/gcc.log && 
                  /usr/local/google/home/raymes/crosstool/chromeos-toolchain/gcctools/chromeos/v14/summarize_results.py /tmp/g++.log""")
blah_job.AddRequiredMachine("", "linux", False)
#blah_job2 = job.Job("mkdir results ; echo \"Installing autotest on\nMYTEST3 FAIL\nMYTEST4 PASS\" > results/results.csv")
#blah_job2.AddRequiredMachine("", "linux", False)
#cat_job = job.Job("cat hello.txt")
#cat_job.AddRequiredMachine("", "linux", False)
#cat_job.AddRequiredFolder(blah_job, "blah.txt", "hello.txt", True)
#cat_job2 = job.Job("cat hello.txt")
#cat_job2.AddRequiredMachine("", "linux", False)
#cat_job2.AddRequiredFolder(cat_job, "hello.txt", "hello.txt", False)
#cat_job2.AddResultsDir("hello.txt")

yes_job = job.Job("yes")
yes_job.AddRequiredMachine("", "linux", False)

group = job_group.JobGroup([blah_job],
                           False, False, baseline_file_src="/tmp/baseline2.csv")

ids = server.ExecuteJobGroup(utils.Serialize(group))

