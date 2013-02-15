import sys
import utils
import os

class Logger(object):

  """Logging helper class."""

  def __init__ (self, rootdir, basefilename, print_console):
    self._logdir = rootdir + "/logs/"
    self.AtomicMkdir(self._logdir)
    self._basefilename = basefilename
    self.cmdfd = open(self._logdir + self._basefilename + ".cmd", "w", 0755)
    self.stdout = open(self._logdir + self._basefilename + ".out", "w")
    self.stderr = open(self._logdir + self._basefilename + ".err", "w")
    self.print_console = print_console

  def Logcmd(self, cmd):
    self.cmdfd.write(str(cmd) + "\n")
    self.cmdfd.flush()
    if self.print_console:
      print "CMD: " + str(cmd)

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

  def LogCommandOutput(self, msg):
    self.stdout.write(msg)
    self.stdout.flush()
    if self.print_console:
      sys.stdout.write(msg)
      sys.stdout.flush()

  def LogCommandError(self, msg):
    self.stderr.write(msg)
    self.stderr.flush()
    if self.print_console:
      sys.stderr.write(msg)
      sys.stderr.flush()

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
