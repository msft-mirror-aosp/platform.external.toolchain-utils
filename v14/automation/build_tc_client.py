import xmlrpclib
from utils import utils
from jobs import p4_job
from jobs import generic_job

server = xmlrpclib.Server("http://localhost:8000")

# TODO: add a setup_chromeos job here.
p4_port = "perforce2:2666"
p4_paths = []
p4_paths.append(("//depot2/gcctools/chromeos/v14/...", "gcctools/chromeos/v14/..."))
###p4_paths.append(("//depot2/gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/...", 
###                 "gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/..."))
p4_revision = 1
p4_checkoutdir = "perforce2"

p4_job = p4_job.P4Job(p4_port, p4_paths, p4_revision, p4_checkoutdir)

build_tc_commands = []
build_tc_commands.append("cd chromeos/src/scripts")
build_tc_commands.append("../../" + p4_checkoutdir + 
                         "/gcctools/chromeos/v14/build_tc.py" +
                         " --toolchain_root=../../" + p4_checkoutdir + "/gcctools")
tc_job = generic_job.GenericJob(build_tc_commands)
tc_job.AddDependency(p4_job)
tc_job.AddRequiredFolders(p4_job, "gcctools")

server.ExecuteJobGroup(utils.Serialize([p4_job, tc_job]))
