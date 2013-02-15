import threading
import jobs.job
import machine_manager
from utils import utils

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

    # Get the machines required
    machines = (self.machine_manager.GetMachines
                (self.job.GetMachineDescriptions()))
    if not machines:
      print "Could not acquire machines for the job"

    primary_machine = machines[0]
    result = utils.RunCommand("ssh %s -- %s" %
                              (primary_machine.name,
                               self.job.GetCommand()), True)
    print result

    # Mark as complete
    self.job.SetStatus(jobs.job.STATUS_COMPLETED)
    self.job_manager.NotifyJobComplete(self.job)



