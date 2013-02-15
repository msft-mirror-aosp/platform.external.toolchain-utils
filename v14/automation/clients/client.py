import xmlrpclib
from utils import utils
from automation.common import job

server = xmlrpclib.Server("http://localhost:8000")

ls_job = job.Job("ls")
ls_job.AddRequiredMachine("", "linux", False)
echo_job = job.Job("echo $PATH")
echo_job.AddRequiredMachine("", "linux", False)
ls_job.AddDependency(echo_job)

server.ExecuteJobGroup(utils.Serialize([ls_job, echo_job]))
