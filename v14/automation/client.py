import StringIO
import job
import xmlrpclib
import pickle
import utils
from jobs import ls_job
from jobs import echo_job

server = xmlrpclib.Server("http://localhost:8000")

echojob = echo_job.EchoJob("hello")
lsjob = ls_job.LSJob("/tmp")
lsjob.AddDependency(echojob)

server.ExecuteJobGroup(utils.Serialize([lsjob, echojob]))
