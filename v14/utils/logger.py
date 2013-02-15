import sys
import utils
import os

class Logger(object):

  """Logging helper class."""

  def __init__ (self, rootdir, basefilename, print_console, subdir="logs"):
    self._logdir = rootdir + "/" + subdir + "/"
    self.AtomicMkdir(self._logdir)
    self._basefilename = basefilename
    self.cmdfd = open(self._logdir + self._basefilename + ".cmd", "w", 0755)
    self.stdout = open(self._logdir + self._basefilename + ".out", "w")
    self.stderr = open(self._logdir + self._basefilename + ".err", "w")
    self.print_console = print_console

  def LogCmd(self, cmd, machine=None, user=None):
    machine_string = ""
    if machine is not None:
      machine_string = machine
    if user is not None:
      machine_string = " (" + user + "@" + machine_string + ")"
    output = "CMD%s: %s\n" % (machine_string, cmd)
    self.cmdfd.write(output)
    self.cmdfd.flush()
    if self.print_console:
      sys.stdout.write(output)
      sys.stdout.flush()

  def LogOutput(self, msg):
    msg = "OUTPUT: " + msg + "\n"
    self.stdout.write(msg)
    self.stdout.flush()
    if self.print_console:
      sys.stdout.write(msg)
      sys.stdout.flush()

  def LogError(self, msg):
    msg = "ERROR: " + msg + "\n"
    self.stderr.write(msg)
    self.stderr.flush()
    if self.print_console:
      sys.stderr.write(msg)
      sys.stderr.flush()

  def LogWarning(self, msg):
    msg = "WARNING: " + msg + "\n"
    self.stderr.write(msg)
    self.stderr.flush()
    if self.print_console:
      sys.stderr.write(msg)
      sys.stderr.flush()

  def LogCommandOutput(self, msg):
    try:
      self.stdout.write(msg)
      if self.print_console:
        sys.stdout.write(msg)
    except StandardError as e:
      print e
      pass

  def LogCommandError(self, msg):
    try:
      self.stderr.write(msg)
      if self.print_console:
        sys.stderr.write(msg)
    except StandardError as e:
      print e
      pass

  def __del__ (self):
    self.cmdfd.close()
    self.stdout.close()
    self.stderr.close()
    return

  def AtomicMkdir(self, newdir):
    try:
      os.makedirs(newdir)
    except OSError:
      print "Warning: Logs directory '%s' already exists." % newdir

main_logger = None


def InitLogger(script_name, print_console=True):
  """Initialize a global logger. To be called only once."""
  global main_logger
  if main_logger != None:
    raise StandardError("The logger has already been initialized")
  (rootdir, basefilename) = utils.GetRoot(script_name)
  main_logger = Logger(rootdir, basefilename, print_console)


def GetLogger():
  if main_logger is None:
    InitLogger(sys.argv[0])
  return main_logger
