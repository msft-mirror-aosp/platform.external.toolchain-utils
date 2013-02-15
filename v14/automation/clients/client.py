import xmlrpclib
from utils import utils
from automation.common import job
from automation.common import job_group
from automation.common.machine_description import MachineSpecification

server = xmlrpclib.Server("http://localhost:8000")

p4client = "~/local/crosstool/chromeos-toolchain"

linux_mach = MachineSpecification(os="linux")

command = ["echo \"executing\"",
           "cp /home/raymes/misc/gcc.log /home/raymes/misc/g++.log .",
           "%s/gcctools/chromeos/v14/summarize_results.py gcc.log" % p4client,
           "%s/gcctools/chromeos/v14/summarize_results.py g++.log" % p4client]

blah_job = job.Job("test_job", " && ".join(command),
                   baseline="/home/raymes/misc/dejagnu_baseline")
blah_job.DependsOnMachine(linux_mach)

if False:
  blah_job2 = job.Job("mkdir results ;"
                      "echo \"Installing autotest on\n"
                      "MYTEST3 FAIL\nMYTEST4 PASS\" > results/results.csv")
  blah_job2.DependsOnMachine(linux_mach)

  cat_job = job.Job("cat hello.txt")
  cat_job.DependsOnMachine(linux_mach)
  cat_job.DependsOnFolder(job.FolderDependency(blah_job, "blah.txt",
                                                 "hello.txt"))
  cat_job2 = job.Job("cat hello.txt")
  cat_job2.DependsOnMachine(linux_mach)
  cat_job2.DependsOnFolder(job.FolderDependency(cat_job, "hello.txt"))

yes_job = job.Job("test_job", "yes")
yes_job.DependsOnMachine(linux_mach)

group = job_group.JobGroup("test_group", [blah_job], False, False)

ids = server.ExecuteJobGroup(utils.Serialize(group))
