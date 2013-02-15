import threading
import job_executer
import automation.common.job
from utils import logger

class JobManager(threading.Thread):

  def __init__(self, machine_manager):
    threading.Thread.__init__(self)
    self.all_jobs = []
    self.ready_jobs = []
    self.job_executer_mapping = {}

    self.machine_manager = machine_manager

    self.job_condition = threading.Condition()

    self.job_counter = 0

    self.listeners = []
    self.listeners.append(self)


  def StartJobManager(self):
    self.job_condition.acquire()
    self.start()
    self.job_condition.notifyAll()
    self.job_condition.release()


  def StopJobManager(self):
    self.job_condition.acquire()
    for job in self.all_jobs:
      self._KillJob(job.id)

    # Signal to die
    self.ready_jobs.insert(0, None)
    self.job_condition.notifyAll()
    self.job_condition.release()

    # Wait for all job threads to finish
    for executer in self.job_executer_mapping.values():
      executer.join()

  # Does not block until the job is completed.
  def KillJob(self, job_id):
    self.job_condition.acquire()
    self._KillJob(job_id)
    self.job_condition.release()

  def GetJob(self, job_id):
    for job in self.all_jobs:
      if job.id == job_id:
        return job
    return None

  def _KillJob(self, job_id):
    logger.GetLogger().LogOutput("Killing job with ID '%s'." % job_id)
    if job_id in self.job_executer_mapping:
      self.job_executer_mapping[job_id].Kill()
    killed_job = None
    for job in self.ready_jobs:
      if job.id == job_id:
        killed_job = job
        self.ready_jobs.remove(killed_job)
        break

  def AddJob(self, current_job):
    self.job_condition.acquire()

    current_job_id = self.job_counter
    current_job.id = current_job_id
    self.job_counter += 1

    self.all_jobs.append(current_job)
    # Only queue a job as ready if it has no dependencies
    if current_job.is_ready:
      self.ready_jobs.append(current_job)

    self.job_condition.notifyAll()
    self.job_condition.release()
    return current_job_id

  def CleanUpJob(self, job):
    self.job_condition.acquire()
    if job.id in self.job_executer_mapping:
      self.job_executer_mapping[job.id].CleanUpWorkDir()
      del self.job_executer_mapping[job.id]
    # TODO(raymes): remove job from self.all_jobs
    self.job_condition.release()


  def NotifyJobComplete(self, job):
    self.machine_manager.ReturnMachines(job.machines)
    self.job_condition.acquire()
    logger.GetLogger().LogOutput("Job profile:\n%s" % str(job))
    if job.status == automation.common.job.STATUS_SUCCEEDED:
      for parent in job.parents:
        if parent.is_ready:
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
        if ready_job is None:
          # Time to die
          self.job_condition.release()
          return


        required_machines = ready_job.required_machines
        for child in ready_job.children:
          required_machines[0].AddPreferredMachine(child.machines[0].name)

        machines = self.machine_manager.GetMachines(required_machines)
        if machines is None:
          # If we can't get the necessary machines right now, simply wait
          # for some jobs to complete
          self.ready_jobs.insert(0, ready_job)
          break
        else:
          # Mark as executing
          executer = job_executer.JobExecuter(ready_job, machines,
                                              self.listeners)
          executer.start()
          self.job_executer_mapping[ready_job.id] = executer



      self.job_condition.release()
