import Queue
import job
import SimpleXMLRPCServer
import threading
import utils

class Server(threading.Thread):

  def __init__(self):
    threading.Thread.__init__(self)
    self.jobs = []
    #TODO(raymes): Can change to PriorityQueue later for fairness
    self.ready_jobs = Queue.Queue()

  def ExecuteJobGroup(self, job_group):
    job_group = utils.Deserialize(job_group)
    for current_job in job_group:
      self.jobs.append(current_job)
      # Only queue a job as ready if it has no dependencies
      if current_job.GetNumDependencies() == 0:
        self.ready_jobs.put(current_job)

  def run(self):
    print "Started server thread."
    while True:
      # Get the next ready job, block if there are none
      ready_job = self.ready_jobs.get(True)

      # Mark as executing and execute
      ready_job.SetStatus(job.STATUS_EXECUTING)
      # Do execute here
      print "EXECUTING: " + ready_job.GetCommand()

      # Mark as complete
      ready_job.SetStatus(job.STATUS_COMPLETED)

      # Schedule all new ready jobs
      for current_job in self.jobs:
        if current_job.IsReady():
          self.ready_jobs.put(current_job)



server = Server()
server.start()
xmlserver = SimpleXMLRPCServer.SimpleXMLRPCServer(("localhost", 8000), allow_none=True)
xmlserver.register_instance(server)
xmlserver.serve_forever()

