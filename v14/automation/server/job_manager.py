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

    self.job_lock = threading.Lock()
    self.job_ready_event = threading.Event()

    self.job_counter = 0

    self.status = JOB_MANAGER_STOPPED

  def StartJobManager(self):
    self.job_lock.acquire()
    if self.status == JOB_MANAGER_STOPPED:
      self.start()
      self.status = JOB_MANAGER_STARTED
    self.job_lock.release()
    self.job_ready_event.set()

  def StopJobManager(self):
    self.job_lock.acquire()
    for job in self.all_jobs:
      self._KillJob(job.GetID())

    if self.status == JOB_MANAGER_STARTED:
      self.status = JOB_MANAGER_STOPPING
    self.job_lock.release()
    self.job_ready_event.set()

  def KillJob(self, job_id):
    self.job_lock.acquire()
    self._KillJob(job_id)
    self.job_lock.release()


  def _KillJob(self, job_id):
    logger.GetLogger().LogOutput("Killing job with ID '%s'." % str(job_id))
    if job_id in self.job_executer_mapping:
      self.job_executer_mapping[job_id].Kill()
    for job in self.ready_jobs:
      if job.GetID() == job_id:
        self.ready_jobs.remove(job)

  def AddJob(self, current_job):
    self.job_lock.acquire()

    current_job_id = self.job_counter
    current_job.SetID(current_job_id)
    self.job_counter += 1

    self.all_jobs.append(current_job)
    # Only queue a job as ready if it has no dependencies
    if current_job.IsReady():
      self.ready_jobs.append(current_job)


    self.job_lock.release()
    self.job_ready_event.set()
    return current_job_id


  def NotifyJobComplete(self, job, status):
    self.job_lock.acquire()
    job.SetStatus(status)
    if status == automation.common.job.STATUS_COMPLETED:
      for parent in job.GetParents():
        if parent.IsReady():
          self.ready_jobs.append(parent)

    del self.job_executer_mapping[job.GetID()]

    self.job_lock.release()
    self.job_ready_event.set()

  def run(self):
    while True:
      # Get the next ready job, block if there are none
      self.job_ready_event.wait()
      self.job_ready_event.clear()

      self.job_lock.acquire()
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
          ready_job.SetStatus(automation.common.job.STATUS_EXECUTING)
          executer = job_executer.JobExecuter(ready_job, machines, self)
          executer.start()
          self.job_executer_mapping[ready_job.GetID()] = executer

      if (self.status == JOB_MANAGER_STOPPING and
          len(self.job_executer_mapping) == 0):
        self.status = JOB_MANAGER_STOPPED
        return


      self.job_lock.release()


