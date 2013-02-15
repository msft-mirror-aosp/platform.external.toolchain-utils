import threading
from automation.common import job
import machine_manager
from utils import utils
from utils import logger
from utils import command_executer

JOBDIR_PREFIX = "/usr/local/google/tmp/automation/job-"

class JobExecuter(threading.Thread):

  def __init__(self, job, machines, job_manager):
    threading.Thread.__init__(self)
    self.cmd_executer = command_executer.GetCommandExecuter()
    self.job = job
    self.job_manager = job_manager
    self.machines = machines

  def run(self):
    # Mark as executing 
    self.job.SetStatus(job.STATUS_EXECUTING)

    # Set job directory
    job_dir = JOBDIR_PREFIX + str(self.job.GetID())
    self.job.SetJobDir(job_dir)

    primary_machine = self.machines[0]
    self.job.SetMachine(primary_machine)

    logger.GetLogger().LogOutput("Executing job with ID '%s' on machine '%s' "
                                 "in directory '%s'" % self.job.GetID(),
                                 self.job.GetMachine(). self.job.GetJobDir())

    rm_success = self.cmd_executer.RunCommand("rm -rf %s" %
                                              self.job.GetJobDir(),
                                              False, primary_machine.name,
                                              primary_machine.username)

    mkdir_success = self.cmd_executer.RunCommand("ssh %s@%s -- mkdir -p %s" %
                            (primary_machine.username, primary_machine.name,
                             self.job.GetWorkDir()))
    for required_folder in self.job.GetRequiredFolders():
      to_folder = self.job.GetWorkDir() + "/" + required_folder.dest
      from_folder = (required_folder.job.GetWorkDir() + "/" +
                     required_folder.src)
      if required_folder.job.GetMachine().name == primary_machine.name:
        # Same machine, do cp
        self.cmd_executer.RunCommand("cp -r %s %s" % (from_folder, to_folder))
      else:
        # Different machine, do scp
        from_machine = required_folder.job.GetMachine().name
        from_user = required_folder.job.GetMachine.username
        to_machine = self.job.GetMachine().name
        to_user = self.job.GetMachine().username
        self.cmd_executer.RunCommand("scp %s@%s:%s %s@%s:%s"
                                % (from_user, from_machine, from_folder,
                                   to_user, to_machine, to_folder))

      command = self.job.GetCommand()
      if command:
        command.replace("$JOB_ID", str(self.job.GetID()))
        quoted_command = utils.FormatQuotedCommand(command)
        print quoted_command
        result = self.cmd_executer.RunCommand("ssh %s@%s -- \"PS1=. TERM=linux "
                                         "source ~/.bashrc ; cd %s && %s\"" %
                                         (primary_machine.username,
                                          primary_machine.name,
                                          self.job.GetWorkDir(),
                                          quoted_command), True)
      else:
        print "Command is empty!"
        result = 1
      print "OUTPUT: " + str(result)

    print "Completed job"
    # Mark as complete
    self.job.SetStatus(job.STATUS_COMPLETED)
    self.job_manager.NotifyJobComplete(self.job)



