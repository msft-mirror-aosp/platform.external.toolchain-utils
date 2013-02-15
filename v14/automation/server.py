import job_manager
import utils
import SimpleXMLRPCServer

class Server:

  def __init__(self):
    #TODO(raymes): Can change to PriorityQueue later for fairness
    self.job_manager = job_manager.JobManager()
    print "Started server thread."
    self.job_manager.start()

  def ExecuteJobGroup(self, job_group):
    job_group = utils.Deserialize(job_group)
    for current_job in job_group:
      self.job_manager.AddJob(current_job)

server = Server()
xmlserver = SimpleXMLRPCServer.SimpleXMLRPCServer(("localhost", 8000),
                                                  allow_none=True)
xmlserver.register_instance(server)
xmlserver.serve_forever()

