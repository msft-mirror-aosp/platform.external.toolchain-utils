import xmlrpclib
from utils import utils
from jobs import p4_job

server = xmlrpclib.Server("http://localhost:8000")

# TODO: add a setup_chromeos job here.
p4_port = "perforce2:2666"
p4_paths = []
p4_paths.append(("//depot2/gcctools/chromeos/v14/...", "gcctools/chromeos/v14/..."))
p4_paths.append(("//depot2/gcctools/gcc/gcc-4.4.3/...", "gcctools/gcc/gcc-4.4.3/..."))
p4_revision = 1
p4_checkoutdir = "perforce2"

p4_job = p4_job.P4Job(p4_port, p4_paths, p4_revision, p4_checkoutdir)

server.ExecuteJobGroup(utils.Serialize([p4_job]))
