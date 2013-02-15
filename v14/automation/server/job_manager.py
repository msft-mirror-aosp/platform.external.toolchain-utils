import threading
import job_executer

JOB_MANAGER_STARTED = 1
JOB_MANAGER_STOPPING = 2
JOB_MANAGER_STOPPED = 3

class JobManager(threading.Thread):

  def __init__(self, machine_manager):
    threading.Thread.__init__(self)
    self.all_jobs = []
    self.ready_jobs = []
    self.pending_jobs = []
    self.executing_jobs = []
    self.completed_jobs = []

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
    if self.status == JOB_MANAGER_STARTED:
      self.status = JOB_MANAGER_STOPPING
    self.job_lock.release()
    self.job_ready_event.set()

  def AddJob(self, current_job):
    self.job_lock.acquire()

    current_job.SetID(self.job_counter)
    self.job_counter += 1

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
    for parent in job.GetParents():
      if parent.IsReady():
        self.ready_jobs.append(parent)
        self.pending_jobs.remove(parent)

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
        machines = self.machine_manager.GetMachines(required_machines)
        if machines is None:
          self.ready_jobs.insert(0, ready_job)
        else:
          executer = job_executer.JobExecuter(ready_job,
                                              machines, self)
          executer.start()


      if self.status == JOB_MANAGER_STOPPING:
        self.status = JOB_MANAGER_STOPPED
        return


      self.job_lock.release()


