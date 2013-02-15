import job_manager
import job_group_manager
from utils import utils
import SimpleXMLRPCServer
import optparse
from utils import command_executer
import machine_manager
import signal
from utils import logger
import sys

def HandleKeyboardInterrupt(signalNumber, frame) :
  server.StopServer()
  sys.exit(1)

class Server:

  def __init__(self, machines_file=machine_manager.DEFAULT_MACHINES_FILE,
               dry_run=False):
    command_executer.InitCommandExecuter(dry_run)
    mm = machine_manager.MachineManager(machines_file)
    self.job_manager = job_manager.JobManager(mm)
    self.job_group_manager = job_group_manager.JobGroupManager(self.job_manager)

  def ExecuteJobGroup(self, job_group, dry_run=False):
    job_group = utils.Deserialize(job_group)
    for job in job_group.GetJobs():
      job.SetDryRun(dry_run)
    job_group_id = self.job_group_manager.AddJobGroup(job_group)
    return job_group_id

  def GetAllJobGroups(self):
    return utils.Serialize(self.job_group_manager.GetAllJobGroups())

  def KillJobGroup(self, job_group_id):
    self.job_manager.KillJobGroup(utils.Deserialize(job_group_id))

  def GetReport(self, job_group_id, summary=False):
    job_group = self.job_group_manager.GetJobGroup(job_group_id)
    if summary == False:
      report = open(job_group.GetTestReport(), 'rb')
      result = "".join(report.readlines())
      report.close()
      return utils.Serialize(result)
    else:
      report = open(job_group.GetTestReport(), 'rb')
      report.readline()
      num_executed = report.readline().split(":")[1].strip()
      num_passes = report.readline().split(":")[1].strip()
      num_failures = report.readline().split(":")[1].strip()
      num_regressions = report.readline().split(":")[1].strip()
      report.close()
      return utils.Serialize((num_executed, num_passes, num_failures,
                             num_regressions))


  def StartServer(self):
    logger.GetLogger().LogOutput("Starting server...")
    self.job_manager.StartJobManager()
    logger.GetLogger().LogOutput("Started server...")

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

