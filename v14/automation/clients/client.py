import xmlrpclib
from utils import utils
from automation.common import job
from automation.common import job_group

server = xmlrpclib.Server("http://localhost:8000")

blah_job = job.Job("echo 'blah blah' > blah.txt")
blah_job.AddRequiredMachine("", "linux", False)
cat_job = job.Job("cat hello.txt")
cat_job.AddRequiredMachine("", "linux", False)
cat_job.AddRequiredFolder(blah_job, "blah.txt", "hello.txt", True)
cat_job2 = job.Job("cat hello.txt")
cat_job2.AddRequiredMachine("", "linux", False)
cat_job2.AddRequiredFolder(cat_job, "hello.txt", "hello.txt", False)
cat_job2.AddResultsDir("hello.txt")

yes_job = job.Job("yes")
yes_job.AddRequiredMachine("", "linux", False)

group = job_group.JobGroup([yes_job],
                           True, True)

ids = server.ExecuteJobGroup(utils.Serialize(group))

