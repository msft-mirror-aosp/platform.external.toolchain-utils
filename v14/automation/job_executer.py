import threading
import jobs.job
import machine_manager
from utils import utils

JOBDIR_PREFIX = "/usr/local/google/home/automation-"

class JobExecuter(threading.Thread):

  def __init__(self, job, machine, job_manager):
    threading.Thread.__init__(self)
    self.job = job
    self.machine = machine
    self.job_manager = job_manager
    self.machine_manager = machine_manager.MachineManager()

  def run(self):
    # Mark as executing and execute
    self.job.SetStatus(jobs.job.STATUS_EXECUTING)

    # Do execute here
    print "EXECUTING: " + self.job.GetCommand()

    # Set job directory
    job_dir = JOBDIR_PREFIX + str(self.job.GetID())
    self.job.SetJobDir(job_dir)

    # Get the machines required
    machines = (self.machine_manager.GetMachines
                (self.job.GetMachineDescriptions()))
    if not machines:
      print "Could not acquire machines for the job"
    else:
      primary_machine = machines[0]
      self.job.SetMachine(primary_machine)

      for required_folder in self.job.GetRequiredFolders():
        to_folder = self.job.GetWorkDirectory() + "/" + required_folder.folder
        from_folder = (required_folder.job.GetWorkDirectory() + "/" +
                         required_folder.folder)
        if required_folder.job.GetMachine().name == primary_machine.name:
          # Same machine, do cp
          utils.RunCommand("cp %s %s", from_folder, to_folder)
        else:
          # Different machine, do scp
          from_machine = required_folder.job.GetMachine().name
          from_user = required_folder.job.GetMachine.username
          to_machine = self.job.GetMachine().name
          to_user = self.job.GetMachine().username
          utils.RunCommand("scp %s@%s:%s %s@%s:%s"
                           % (from_user, from_machine, from_folder, to_user,
                              to_machine, to_folder))

      utils.RunCommand("ssh %s@%s -- mkdir -p %s" %
                                (primary_machine.username, primary_machine.name,
                                 self.job.GetJobDir()))
      utils.RunCommand("ssh %s@%s -- mkdir -p %s" %
                                (primary_machine.username, primary_machine.name,
                                 self.job.GetWorkDir()))
      result = utils.RunCommand("ssh %s@%s -- \"cd %s && %s\"" %
                                (primary_machine.username, primary_machine.name,
                                 self.job.GetWorkDir(),
                                 self.job.GetCommand()), True)
      print "OUTPUT: " + str(result)

    print "Completed job"
    # Mark as complete
    self.job.SetStatus(jobs.job.STATUS_COMPLETED)
    self.job_manager.NotifyJobComplete(self.job)



