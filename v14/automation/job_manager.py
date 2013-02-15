import threading
import job_executer


class JobManager(threading.Thread):

  def __init__(self):
    threading.Thread.__init__(self)
    self.all_jobs = []
    self.ready_jobs = []
    self.pending_jobs = []
    self.executing_jobs = []
    self.completed_jobs = []

    self.job_lock = threading.Lock()
    self.job_ready_event = threading.Event()

  def AddJob(self, current_job):
    self.job_lock.acquire()

    self.all_jobs.append(current_job)
    # Only queue a job as ready if it has no dependencies
    if current_job.IsReady():
      self.ready_jobs.append(current_job)
    else:
      self.pending_jobs.append(current_job)

    self.job_lock.release()
    self.job_ready_event.set()


  def NotifyJobComplete(self, job):
    self.job_lock.acquire()
    for dependent in job.GetDependents():
      if dependent.IsReady():
        self.ready_jobs.append(dependent)
        self.pending_jobs.remove(dependent)

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

        executer = job_executer.JobExecuter(ready_job, None, self)
        executer.start()

      self.job_lock.release()
