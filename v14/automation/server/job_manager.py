import threading
import job_executer
import automation.common.job
from utils import logger

JOB_MANAGER_STARTED = 1
JOB_MANAGER_STOPPING = 2
JOB_MANAGER_STOPPED = 3

class JobManager(threading.Thread):

  def __init__(self, machine_manager):
    threading.Thread.__init__(self)
    self.all_jobs = []
    self.ready_jobs = []
    self.job_executer_mapping = {}

    self.machine_manager = machine_manager

    self.job_condition = threading.Condition()

    self.job_counter = 0

    self.status = JOB_MANAGER_STOPPED

    self.listeners = []
    self.listeners.append(self)


  def StartJobManager(self):
    self.job_condition.acquire()
    if self.status == JOB_MANAGER_STOPPED:
      self.start()
      self.status = JOB_MANAGER_STARTED
    self.job_condition.notifyAll()
    self.job_condition.release()


  def StopJobManager(self):
    self.job_condition.acquire()
    for job in self.all_jobs:
      self._KillJob(job.GetID())

    if self.status == JOB_MANAGER_STARTED:
      self.status = JOB_MANAGER_STOPPING
    self.job_condition.notifyAll()
    self.job_condition.release()

    # Wait for all job threads to finish
    for executer in self.job_executer_mapping.values():
      executer.join()

  def KillJob(self, job_id):
    self.job_condition.acquire()
    self._KillJob(job_id)
    self.job_condition.release()

  def _KillJob(self, job_id):
    logger.GetLogger().LogOutput("Killing job with ID '%s'." % str(job_id))
    if job_id in self.job_executer_mapping:
      self.job_executer_mapping[job_id].Kill()
    killed_job = None
    for job in self.ready_jobs:
      if job.GetID() == job_id:
        killed_job = job
        self.ready_jobs.remove(killed_job)
        break

  def AddJob(self, current_job):
    self.job_condition.acquire()
    # Don't add job if we are about to die.
    if self.status != JOB_MANAGER_STARTED:
      self.job_condition.release()
      return

    current_job_id = self.job_counter
    current_job.SetID(current_job_id)
    self.job_counter += 1

    self.all_jobs.append(current_job)
    # Only queue a job as ready if it has no dependencies
    if current_job.IsReady():
      self.ready_jobs.append(current_job)

    self.job_condition.notifyAll()
    self.job_condition.release()
    return current_job_id

  def CleanUpJob(self, job):
    self.job_executer_mapping[job.GetID()].CleanUp()
    del self.job_executer_mapping[job.GetID()]


  def NotifyJobComplete(self, job, status):
    self.job_condition.acquire()
    job.SetStatus(status)
    if status == automation.common.job.STATUS_COMPLETED:
      for parent in job.GetParents():
        if parent.IsReady():
          if parent not in self.ready_jobs:
            self.ready_jobs.append(parent)

    self.job_condition.notifyAll()
    self.job_condition.release()

  def AddListener(self, listener):
    self.listeners.append(listener)

  def run(self):
    while True:
      # Get the next ready job, block if there are none
      self.job_condition.acquire()
      self.job_condition.wait()
      while len(self.ready_jobs) > 0:

        ready_job = self.ready_jobs.pop()

        required_machines = ready_job.GetRequiredMachines()
        for child in ready_job.GetChildren():
          required_machines[0].AddPreferredMachine(child.GetMachines()[0].name)

        machines = self.machine_manager.GetMachines(required_machines)
        if machines is None:
          # If we can't get the necessary machines right now, simply wait
          # for some jobs to complete
          self.ready_jobs.insert(0, ready_job)
        else:
          # Mark as executing 
          ready_job.SetStatus(automation.common.job.STATUS_SETUP)
          executer = job_executer.JobExecuter(ready_job, machines,
                                              self.listeners)
          executer.start()
          self.job_executer_mapping[ready_job.GetID()] = executer

      if self.status == JOB_MANAGER_STOPPING:
        self.status = JOB_MANAGER_STOPPED
        self.job_condition.release()
        return


      self.job_condition.release()


