#!/usr/bin/python

import optparse
import sys
import setup_chromeos

from dejagnu import gdb_dejagnu
from utils import command_executer
from utils import email_sender


class DejagnuAdapter(object):

  def __init__(self, board, remote, gdb_dir,
               chromeos_root, cleanup):
    self._board = board
    self._remote = remote
    self._gdb_dir = gdb_dir
    self._chromeos_root = chromeos_root
    self._cleanup = cleanup
    self._cmd_exec = command_executer.GetCommandExecuter()

  def SetupChromeOS(self):
    cmd = [setup_chromeos.__file__,
           '--dir=' + self._chromeos_root, '--minilayout', '--jobs=8']
    ret = setup_chromeos.Main(cmd)
    if ret:
      raise Exception('Failed to checkout chromeos')
    ## Do cros_sdk and setup_board, otherwise build_tc in next step will fail.
    cmd = 'cd {0} && cros_sdk --download'.format(self._chromeos_root)
    ret = self._cmd_exec.RunCommand(cmd, terminated_timeout=9000)
    if ret:
      raise Exception('Failed to create chroot.')

  def SetupBoard(self):
    cmd = './setup_board --board=' + self._board
    ret = self._cmd_exec.ChrootRunCommand(self._chromeos_root,
                                          cmd, terminated_timeout=4000)
    if ret:
      raise Exception('Failed to setup board.')

  def CheckGDB(self):
    args = [gdb_dejagnu.__file__,
            '--board=' + self._board,
            '--chromeos_root=' + self._chromeos_root,
            '--mount=' + self._gdb_dir,
            '--remote=' + self._remote]
    if self._cleanup:
      args.append('--cleanup=' + self._cleanup)
    return gdb_dejagnu.Main(args)


# Parse the output log to determine how many failures we have.
# Return -1 if parse output log failed.
def GetNumNewFailures(string):
  if not string:
    return 0
  return len(string.splitlines())


# Do not throw any exception in this function!
def EmailResult(result):
  email_to = ['yunlian@google.com']
  if len(result) == 4:
    subject = 'Job failed: dejagnu test didn\'t finish'
    email_text = ('Job failed prematurely, check exception below.\n' +
                  result[3])
  elif result[0]:
    subject = 'Job finished: dejagnu test failed'
    num_new_failures = GetNumNewFailures(result[1])
    if num_new_failures >= 0:
      summary = '{0} new fail(s), check log below.'.format(num_new_failures)
    else:
      summary = 'At least 1 new fail found, check log below.'
    email_text = (summary +
                  ('\nStdout ====\n'
                   '{0}\n'
                   '\nStderr ===\n'
                   '{1}\n').format(result[1], result[2]))
  else:
    subject = 'Job finished: dejagnu test passed'
    email_text = ('Cool! No new fail found.\n'
                  '\nStdout ====\n'
                  '{0}\n'
                  '\nStderr ====\n'
                  '{1}\n').format(result[1], result[2])

  try:
    email_sender.EmailSender().SendEmail(email_to, subject, email_text)
    print 'Email sent.'
  except Exception as e:
    # Do not propagate this email sending exception, you want to email an
    # email exception? Just log it on console.
    print ('Sending email failed - {0}'
           'Subject: {1}'
           'Text: {2}').format(
               str(e), subject, email_text)


def ProcessArguments(argv):
  """Processing script arguments."""
  parser = optparse.OptionParser(description=(
      'This script is used by nightly client to test gdb. '
      'DO NOT run it unless you know what you are doing.'),
                                 usage='test_gdb_dejagnu.py options')
  parser.add_option('-b', '--board', dest='board',
                    help=('Required. Specify board type. For example '
                          '\'lumpy\' and \'daisy\''))
  parser.add_option('-r', '--remote', dest='remote',
                    help=('Required. Specify remote board address'))
  parser.add_option('-g', '--gdb_dir', dest='gdb_dir', default='',
                    help=('Optional. Specify gdb checkout directory.'))
  parser.add_option('-c', '--chromeos_root', dest='chromeos_root',
                    default='chromeos.live',
                    help=('Optional. Specify chromeos checkout directory.'))
  parser.add_option('--cleanup', dest='cleanup', default=None,
                    help=('Optional. Do cleanup after the test.'))

  options, _ = parser.parse_args(argv)

  if not options.board or not options.remote:
    raise Exception('--board and --remote are mandatory options.')

  return options


def Main(argv):
  opt = ProcessArguments(argv)
  print opt
  adapter = DejagnuAdapter(
      opt.board, opt.remote, opt.gdb_dir, opt.chromeos_root,
      opt.cleanup)
  try:
    adapter.SetupChromeOS()
    adapter.SetupBoard()
    ret = adapter.CheckGDB()
  except Exception as e:
    print e
    ret = (1, '', '', str(e))
  finally:
    EmailResult(ret)
    return ret

if  __name__ == '__main__':
  retval = Main(sys.argv)
  sys.exit(retval[0])
