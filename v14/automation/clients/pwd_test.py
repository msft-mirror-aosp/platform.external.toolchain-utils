import xmlrpclib
from utils import utils
from automation.common import job
from automation.common import job_group
from automation.common.machine_description import MachineSpecification

server = xmlrpclib.Server("http://localhost:8000")

command = ["echo These following 3 lines should be the same",
           "pwd",
           "$(pwd)",
           "echo ${PWD}"]

pwd_job = job.Job("pwd_job", " && ".join(command))
pwd_job.DependsOnMachine(MachineSpecification(os="linux"))

job_group = job_group.JobGroup("pwd_client", [pwd_job])
ids = server.ExecuteJobGroup(utils.Serialize(job_group))
