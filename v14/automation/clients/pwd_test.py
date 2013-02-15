import xmlrpclib
from utils import utils
from automation.common import job
from automation.common import job_group

server = xmlrpclib.Server("http://localhost:8000")

command = "echo These following 3 lines should be the same"
command += "&& pwd"
command += "&& echo $(pwd)"
command += "&& echo ${PWD}"

pwd_job = job.Job("pwd_job", command)
pwd_job.AddRequiredMachine("", "linux", False)

job_group = job_group.JobGroup("pwd_client", [pwd_job])
ids = server.ExecuteJobGroup(utils.Serialize(job_group))

