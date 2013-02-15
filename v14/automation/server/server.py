import job_manager
from utils import utils
import SimpleXMLRPCServer
import optparse
from utils import command_executer
import machine_manager

class Server:

  def __init__(self, machines_file=machine_manager.DEFAULT_MACHINES_FILE,
               dry_run=False):
    command_executer.InitCommandExecuter(dry_run)
    mm = machine_manager.MachineManager(machines_file)
    self.job_manager = job_manager.JobManager(mm)


  def ExecuteJobGroup(self, job_group):
    #TODO(raymes): Verify that the job graph is valid. I.e. every
    # dependency has been transmitted to the server.
    job_group = utils.Deserialize(job_group)
    for current_job in job_group:
      self.job_manager.AddJob(current_job)


  def GetAllJobs(self):
    jobs_dict = {}
    jobs_dict["all"] = self.job_manager.all_jobs
    jobs_dict["ready"] = self.job_manager.ready_jobs
    jobs_dict["pending"] = self.job_manager.pending_jobs
    jobs_dict["executing"] = self.job_manager.executing_jobs
    jobs_dict["completed"] = self.job_manager.completed_jobs


  def StartServer(self):
    print "Started server thread."
    self.job_manager.StartJobManager()

  def StopServer(self):
    self.job_manager.StopJobManager()

if __name__ == "__main__":
  parser = optparse.OptionParser()
  parser.add_option("-m", "--machines-file", dest="machines_file",
                    help="The location of the file "
                    "containing the machines database",
                    default=machine_manager.DEFAULT_MACHINES_FILE)
  parser.add_option("-n", "--dry-run", dest="dry_run",
                    help="Start the server in dry-run mode, where jobs will "
                    "not actually be executed.",
                    action="store_true", default=False)
  options = parser.parse_args()[0]
  server = Server(options.machines_file, options.dry_run)
  server.StartServer()
  xmlserver = SimpleXMLRPCServer.SimpleXMLRPCServer(("localhost", 8000),
                                                  allow_none=True)
  xmlserver.register_instance(server)
  try:
    xmlserver.serve_forever()
  except (KeyboardInterrupt, SystemExit):
    print "Caught exception... Cleaning up."
    server.StopServer()
    raise


