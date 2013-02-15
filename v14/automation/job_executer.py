import threading
import jobs.job

class JobExecuter(threading.Thread):

  def __init__(self, job, machine, job_manager):
    threading.Thread.__init__(self)
    self.job = job
    self.machine = machine
    self.job_manager = job_manager

  def run(self):
    # Mark as executing and execute
    self.job.SetStatus(jobs.job.STATUS_EXECUTING)

    # Do execute here
    print "EXECUTING: " + self.job.GetCommand()
    machine = "localhost"

    # Mark as complete
    self.job.SetStatus(jobs.job.STATUS_COMPLETED)
    self.job_manager.NotifyJobComplete(self.job)



