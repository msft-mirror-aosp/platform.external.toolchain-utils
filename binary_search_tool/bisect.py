#!/usr/bin/python2
"""The unified package/object bisecting tool."""

from __future__ import print_function

import abc
import argparse
import os
import sys
from argparse import RawTextHelpFormatter

import common

from utils import command_executer
from utils import logger

import binary_search_state


class Bisector(object):
  """The abstract base class for Bisectors."""

  # Make Bisector an abstract class
  __metaclass__ = abc.ABCMeta

  def __init__(self, options, overrides=None):
    """Constructor for Bisector abstract base class

    Args:
      options: positional arguments for specific mode (board, remote, etc.)
      overrides: optional dict of overrides for argument defaults
    """
    self.options = options
    self.overrides = overrides
    if not overrides:
      self.overrides = {}
    self.logger = logger.GetLogger()
    self.ce = command_executer.GetCommandExecuter()

  def _PrettyPrintArgs(self, args, overrides):
    """Output arguments in a nice, human readable format

    Will print and log all arguments for the bisecting tool and make note of
    which arguments have been overridden.

    Example output:
      ./bisect.py package daisy 172.17.211.184 -I "" -t cros_pkg/my_test.sh
      Performing ChromeOS Package bisection
      Method Config:
        board : daisy
       remote : 172.17.211.184

      Bisection Config: (* = overridden)
         get_initial_items : cros_pkg/get_initial_items.sh
            switch_to_good : cros_pkg/switch_to_good.sh
             switch_to_bad : cros_pkg/switch_to_bad.sh
       *    install_script :
       *       test_script : cros_pkg/my_test.sh
                     prune : True
             noincremental : False
                 file_args : True

    Args:
      args: The args to be given to binary_search_state.Run. This represents
            how the bisection tool will run (with overridden arguments already
            added in).
      overrides: The dict of overriden arguments provided by the user. This is
                 provided so the user can be told which arguments were
                 overriden and with what value.
    """
    # Output method config (board, remote, etc.)
    options = vars(self.options)
    out = '\nPerforming %s bisection\n' % self.method_name
    out += 'Method Config:\n'
    max_key_len = max([len(str(x)) for x in options.keys()])
    for key in sorted(options):
      val = options[key]
      key_str = str(key).rjust(max_key_len)
      val_str = str(val)
      out += ' %s : %s\n' % (key_str, val_str)

    # Output bisection config (scripts, prune, etc.)
    out += '\nBisection Config: (* = overridden)\n'
    max_key_len = max([len(str(x)) for x in args.keys()])
    # Print args in common._ArgsDict order
    args_order = [x['dest'] for x in common.GetArgsDict().itervalues()]
    compare = lambda x, y: cmp(args_order.index(x), args_order.index(y))

    for key in sorted(args, cmp=compare):
      val = args[key]
      key_str = str(key).rjust(max_key_len)
      val_str = str(val)
      changed_str = '*' if key in overrides else ' '

      out += ' %s %s : %s\n' % (changed_str, key_str, val_str)

    out += '\n'
    self.logger.LogOutput(out)

  def ArgOverride(self, args, overrides, pretty_print=True):
    """Override arguments based on given overrides and provide nice output

    Args:
      args: dict of arguments to be passed to binary_search_state.Run (runs
            dict.update, causing args to be mutated).
      overrides: dict of arguments to update args with
      pretty_print: if True print out args/overrides to user in pretty format
    """
    args.update(overrides)
    if pretty_print:
      self._PrettyPrintArgs(args, overrides)

  @abc.abstractmethod
  def PreRun(self):
    pass

  @abc.abstractmethod
  def Run(self):
    pass

  @abc.abstractmethod
  def PostRun(self):
    pass


class BisectPackage(Bisector):
  """The class for package bisection steps."""

  cros_pkg_setup = 'cros_pkg/setup.sh'
  cros_pkg_cleanup = 'cros_pkg/%s_cleanup.sh'

  def __init__(self, options, overrides):
    super(BisectPackage, self).__init__(options, overrides)
    self.method_name = 'ChromeOS Package'
    self.default_kwargs = {
        'get_initial_items': 'cros_pkg/get_initial_items.sh',
        'switch_to_good': 'cros_pkg/switch_to_good.sh',
        'switch_to_bad': 'cros_pkg/switch_to_bad.sh',
        'install_script': 'cros_pkg/install.sh',
        'test_script': 'cros_pkg/interactive_test.sh',
        'noincremental': False,
        'prune': True,
        'file_args': True
    }
    self.ArgOverride(self.default_kwargs, self.overrides)

  def PreRun(self):
    cmd = ('%s %s %s' %
           (self.cros_pkg_setup, self.options.board, self.options.remote))
    ret, _, _ = self.ce.RunCommandWExceptionCleanup(cmd, print_to_console=True)
    if ret:
      self.logger.LogError('Package bisector setup failed w/ error %d' % ret)
      return 1
    return 0

  def Run(self):
    return binary_search_state.Run(**self.default_kwargs)

  def PostRun(self):
    cmd = self.cros_pkg_cleanup % self.options.board
    ret, _, _ = self.ce.RunCommandWExceptionCleanup(cmd, print_to_console=True)
    if ret:
      self.logger.LogError('Package bisector cleanup failed w/ error %d' % ret)
      return 1
    return 0


class BisectObject(Bisector):
  """The class for object bisection steps."""

  def __init__(self, options, overrides):
    super(BisectObject, self).__init__(options, overrides)

  def PreRun(self):
    raise NotImplementedError('Object bisecting still WIP')

  def Run(self):
    return 1

  def PostRun(self):
    return 1


def Run(bisector):
  log = logger.GetLogger()

  log.LogOutput('Setting up Bisection tool')
  ret = bisector.PreRun()
  if ret:
    return ret

  log.LogOutput('Running Bisection tool')
  ret = bisector.Run()
  if ret:
    return ret

  log.LogOutput('Cleaning up Bisection tool')
  ret = bisector.PostRun()
  if ret:
    return ret

  return 0


_HELP_EPILOG = """
Run ./bisect.py {method} --help for individual method help/args

------------------

See README.bisect for examples on argument overriding

See below for full override argument reference:
"""


def Main(argv):
  override_parser = argparse.ArgumentParser(add_help=False,
                                            argument_default=argparse.SUPPRESS,
                                            usage='bisect.py {mode} [options]')
  common.BuildArgParser(override_parser, override=True)

  epilog = _HELP_EPILOG + override_parser.format_help()
  parser = argparse.ArgumentParser(epilog=epilog,
                                   formatter_class=RawTextHelpFormatter)
  subparsers = parser.add_subparsers(title='Bisect mode',
                                     description=('Which bisection method to '
                                                  'use. Each method has '
                                                  'specific setup and '
                                                  'arguments. Please consult '
                                                  'the README for more '
                                                  'information.'))

  parser_package = subparsers.add_parser('package')
  parser_package.add_argument('board', help='Board to target')
  parser_package.add_argument('remote', help='Remote machine to test on')
  parser_package.set_defaults(handler=BisectPackage)

  parser_object = subparsers.add_parser('object')
  parser_object.set_defaults(handler=BisectObject)

  options, remaining = parser.parse_known_args(argv)
  if remaining:
    overrides = override_parser.parse_args(remaining)
    overrides = vars(overrides)
  else:
    overrides = {}

  subcmd = options.handler
  del options.handler

  bisector = subcmd(options, overrides)
  return Run(bisector)


if __name__ == '__main__':
  os.chdir(os.path.dirname(__file__))
  sys.exit(Main(sys.argv[1:]))
