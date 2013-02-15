import job_manager
from utils import utils
import SimpleXMLRPCServer
import optparse
from utils import command_executer
import machine_manager
import signal
from utils import logger
import sys
import socket

def HandleKeyboardInterrupt(signalNumber, frame) :
  server.StopServer()
  sys.exit(1)

class Server:

  def __init__(self, machines_file=machine_manager.DEFAULT_MACHINES_FILE,
               dry_run=False):
    command_executer.InitCommandExecuter(dry_run)
    mm = machine_manager.MachineManager(machines_file)
    self.job_manager = job_manager.JobManager(mm)


  def ExecuteJobGroup(self, job_group):
    #TODO(raymes): Verify that the job graph is valid. I.e. every
    # dependency has been transmitted to the server.
    # Check that all jobs have a required machine
    ids = []
    job_group = utils.Deserialize(job_group)
    for current_job in job_group:
      id = self.job_manager.AddJob(current_job)
      ids.append(id)
    return ids

  def GetAllJobs(self):
    jobs_dict = {}
    jobs_dict["all"] = self.job_manager.all_jobs
    jobs_dict["ready"] = self.job_manager.ready_jobs

  def KillJob(self, job_id):
    self.job_manager.KillJob(utils.Deserialize(job_id))

  def StartServer(self):
    logger.GetLogger().LogOutput("Starting server...")
    self.job_manager.StartJobManager()

  def StopServer(self):
    logger.GetLogger().LogOutput("Stopping server...")
    self.job_manager.StopJobManager()
    self.job_manager.join()
    logger.GetLogger().LogOutput("Stopped server.")

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
  global server
  server = Server(options.machines_file, options.dry_run)
  signal.signal(signal.SIGINT, HandleKeyboardInterrupt)
  server.StartServer()
  try:
    xmlserver = SimpleXMLRPCServer.SimpleXMLRPCServer(("localhost", 8000),
                                                      allow_none=True)
  except StandardError as e:
    logger.GetLogger().LogError(str(e))
    server.StopServer()
    sys.exit(1)
  xmlserver.register_instance(server)
  xmlserver.serve_forever()

