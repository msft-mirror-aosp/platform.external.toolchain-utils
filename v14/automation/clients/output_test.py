import xmlrpclib
import sys
from utils import utils
from automation.common import job
from automation.common import job_group
from automation.common.machine_description import MachineSpecification

server = xmlrpclib.Server("http://localhost:8000")

command = "%s/../../produce_output.py" % utils.GetRoot(sys.argv[0])[0]

pwd_job = job.Job("pwd_job", command)
pwd_job.DependsOnMachine(MachineSpecification(os="linux"))

job_group = job_group.JobGroup("pwd_client", [pwd_job])
ids = server.ExecuteJobGroup(utils.Serialize(job_group))
