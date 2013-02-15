import xmlrpclib
import sys
from utils import utils
from automation.common import job
from automation.common import job_group

server = xmlrpclib.Server("http://localhost:8000")

lowlevel_script = (utils.GetRoot(sys.argv[0])[0] +
                   "/../../produce_output.py")
command = lowlevel_script

pwd_job = job.Job("pwd_job", command)
pwd_job.AddRequiredMachine("", "linux", False)

job_group = job_group.JobGroup("pwd_client", [pwd_job])
ids = server.ExecuteJobGroup(utils.Serialize(job_group))

