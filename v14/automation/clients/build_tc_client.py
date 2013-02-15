import xmlrpclib
from utils import utils
from automation.common import job
from automation.common import jobs_helper

server = xmlrpclib.Server("http://localhost:8000")

# TODO: add a setup_chromeos job here.
p4_port = "perforce2:2666"
p4_paths = []
p4_paths.append(("//depot2/gcctools/chromeos/v14/...", "gcctools/chromeos/v14/..."))
p4_paths.append(("//depot2/gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/...",
                 "gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/..."))
p4_revision = 1
p4_checkoutdir = "perforce2"

p4_job = jobs_helper.CreateP4Job(p4_port, p4_paths, p4_revision, p4_checkoutdir)
setup_chromeos_job = jobs_helper.CreateSetupChromeOSJob(p4_job, "latest")

build_tc_commands = []
build_tc_commands.append(p4_checkoutdir +
                         "/gcctools/chromeos/v14/build_tc.py" +
                         " --toolchain_root=" + p4_checkoutdir + "/gcctools" +
                         " --chromeos_root=" + "chromeos")
tc_job = job(build_tc_commands)
tc_job.AddDependency(p4_job)
tc_job.AddRequiredFolder(p4_job, "perforce2", "perforce2")
tc_job.AddDependency(setup_chromeos_job)
tc_job.AddRequiredFolder(setup_chromeos_job, "chromeos", "chromeos")

server.ExecuteJobGroup(utils.Serialize([p4_job, setup_chromeos_job, tc_job]))
