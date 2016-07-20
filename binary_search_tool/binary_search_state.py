#!/usr/bin/python2
"""The binary search wrapper."""

from __future__ import print_function

import argparse
import math
import os
import pickle
import sys
import tempfile
import time

# Adds cros_utils to PYTHONPATH
import common

# Now we do import from cros_utils
from cros_utils import command_executer
from cros_utils import logger

import binary_search_perforce

STATE_FILE = '%s.state' % sys.argv[0]
HIDDEN_STATE_FILE = os.path.join(
    os.path.dirname(STATE_FILE), '.%s' % os.path.basename(STATE_FILE))

class Error(Exception):
  """The general binary search tool error class."""
  pass


class BinarySearchState(object):
  """The binary search state class."""

  def __init__(self, get_initial_items, switch_to_good, switch_to_bad,
               install_script, test_script, incremental, prune, iterations,
               prune_iterations, verify_level, file_args, verbose):
    """BinarySearchState constructor, see Run for full args documentation."""
    self.get_initial_items = get_initial_items
    self.switch_to_good = switch_to_good
    self.switch_to_bad = switch_to_bad
    self.install_script = install_script
    self.test_script = test_script
    self.incremental = incremental
    self.prune = prune
    self.iterations = iterations
    self.prune_iterations = prune_iterations
    self.verify_level = verify_level
    self.file_args = file_args
    self.verbose = verbose

    self.l = logger.GetLogger()
    self.ce = command_executer.GetCommandExecuter()

    self.resumed = False
    self.prune_cycles = 0
    self.search_cycles = 0
    self.binary_search = None
    self.all_items = None
    self.PopulateItemsUsingCommand(self.get_initial_items)
    self.currently_good_items = set([])
    self.currently_bad_items = set([])
    self.found_items = set([])

    self.start_time = time.time()

  def SwitchToGood(self, item_list):
    """Switch given items to "good" set."""
    if self.incremental:
      self.l.LogOutput('Incremental set. Wanted to switch %s to good' %
                       str(item_list), print_to_console=self.verbose)
      incremental_items = [
          item for item in item_list if item not in self.currently_good_items
      ]
      item_list = incremental_items
      self.l.LogOutput('Incremental set. Actually switching %s to good' %
                       str(item_list), print_to_console=self.verbose)

    if not item_list:
      return

    self.l.LogOutput('Switching %s to good' % str(item_list),
                     print_to_console=self.verbose)
    self.RunSwitchScript(self.switch_to_good, item_list)
    self.currently_good_items = self.currently_good_items.union(set(item_list))
    self.currently_bad_items.difference_update(set(item_list))

  def SwitchToBad(self, item_list):
    """Switch given items to "bad" set."""
    if self.incremental:
      self.l.LogOutput('Incremental set. Wanted to switch %s to bad' %
                       str(item_list), print_to_console=self.verbose)
      incremental_items = [
          item for item in item_list if item not in self.currently_bad_items
      ]
      item_list = incremental_items
      self.l.LogOutput('Incremental set. Actually switching %s to bad' %
                       str(item_list), print_to_console=self.verbose)

    if not item_list:
      return

    self.l.LogOutput('Switching %s to bad' % str(item_list),
                     print_to_console=self.verbose)
    self.RunSwitchScript(self.switch_to_bad, item_list)
    self.currently_bad_items = self.currently_bad_items.union(set(item_list))
    self.currently_good_items.difference_update(set(item_list))

  def RunSwitchScript(self, switch_script, item_list):
    """Pass given items to switch script.

    Args:
      switch_script: path to switch script
      item_list: list of all items to be switched
    """
    if self.file_args:
      with tempfile.NamedTemporaryFile() as f:
        f.write('\n'.join(item_list))
        f.flush()
        command = '%s %s' % (switch_script, f.name)
        ret, _, _ = self.ce.RunCommandWExceptionCleanup(
            command, print_to_console=self.verbose)
    else:
      command = '%s %s' % (switch_script, ' '.join(item_list))
      ret, _, _ = self.ce.RunCommandWExceptionCleanup(
          command, print_to_console=self.verbose)
    assert ret == 0, 'Switch script %s returned %d' % (switch_script, ret)

  def TestScript(self):
    """Run test script and return exit code from script."""
    command = self.test_script
    ret, _, _ = self.ce.RunCommandWExceptionCleanup(command)
    return ret

  def InstallScript(self):
    """Run install script and return exit code from script."""
    if not self.install_script:
      return 0

    command = self.install_script
    ret, _, _ = self.ce.RunCommandWExceptionCleanup(command)
    return ret

  def DoVerify(self):
    """Verify correctness of test environment.

    Verify that a "good" set of items produces a "good" result and that a "bad"
    set of items produces a "bad" result. To be run directly before running
    DoSearch. If verify_level is 0 this step is skipped.
    """
    if not self.verify_level:
      return

    self.l.LogOutput('VERIFICATION')
    self.l.LogOutput('Beginning %d tests to verify good/bad sets\n' %
                     self.verify_level)
    for _ in range(int(self.verify_level)):
      self.l.LogOutput('Resetting all items to good to verify.')
      self.SwitchToGood(self.all_items)
      status = self.InstallScript()
      assert status == 0, 'When reset_to_good, install should succeed.'
      status = self.TestScript()
      assert status == 0, 'When reset_to_good, status should be 0.'

      self.l.LogOutput('Resetting all items to bad to verify.')
      self.SwitchToBad(self.all_items)
      status = self.InstallScript()
      assert status == 0, 'When reset_to_bad, install should succeed.'
      status = self.TestScript()
      assert status == 1, 'When reset_to_bad, status should be 1.'

  def DoSearch(self):
    """Perform full search for bad items.

    Perform full search until prune_iterations number of bad items are found.
    """
    while (True and
           len(self.all_items) > 1 and
           self.prune_cycles < self.prune_iterations):
      terminated = self.DoBinarySearch()
      self.prune_cycles += 1
      if not terminated:
        break
      # Prune is set.
      prune_index = self.binary_search.current

      # If already seen item we have no new bad items to find, finish up
      if self.all_items[prune_index] in self.found_items:
        self.l.LogOutput(('Found item already found before: %s. '
                          'Done searching.' % self.all_items[prune_index]))
        self.l.LogOutput('Bad items are: %s' %
                         ' '.join(self.found_items))
        break

      new_all_items = list(self.all_items)
      # Move prune item to the end of the list.
      new_all_items.append(new_all_items.pop(prune_index))
      self.found_items.add(new_all_items[-1])

      if prune_index:
        new_all_items = new_all_items[prune_index - 1:]

      self.l.LogOutput('Old list: %s. New list: %s' % (str(self.all_items),
                                                       str(new_all_items)),
                       print_to_console=self.verbose)

      if not self.prune:
        self.l.LogOutput('Not continuning further, --prune is not set')
        break
      # FIXME: Do we need to Convert the currently good items to bad
      self.PopulateItemsUsingList(new_all_items)

  def DoBinarySearch(self):
    """Perform single iteration of binary search."""
    # If in resume mode don't reset search_cycles
    if not self.resumed:
      self.search_cycles = 0
    else:
      self.resumed = False

    terminated = False
    while self.search_cycles < self.iterations and not terminated:
      self.SaveState()
      self.OutputProgress()

      self.search_cycles += 1
      [bad_items, good_items] = self.GetNextItems()

      # TODO: bad_items should come first.
      self.SwitchToGood(good_items)
      self.SwitchToBad(bad_items)
      status = self.InstallScript()
      if status == 0:
        status = self.TestScript()
      else:
        # Install script failed, treat as skipped item
        status = 2
      terminated = self.binary_search.SetStatus(status)

      if terminated:
        self.l.LogOutput('Terminated!')
    if not terminated:
      self.l.LogOutput('Ran out of iterations searching...')
    self.l.LogOutput(str(self), print_to_console=self.verbose)
    return terminated

  def PopulateItemsUsingCommand(self, command):
    """Update all_items and binary search logic from executable.

    This method is mainly required for enumerating the initial list of items
    from the get_initial_items script.

    Args:
      command: path to executable that will enumerate items.
    """
    ce = command_executer.GetCommandExecuter()
    _, out, _ = ce.RunCommandWExceptionCleanup(command,
                                               return_output=True,
                                               print_to_console=self.verbose)
    all_items = out.split()
    self.PopulateItemsUsingList(all_items)

  def PopulateItemsUsingList(self, all_items):
    """Update all_items and binary searching logic from list.

    Args:
      all_items: new list of all_items
    """
    self.all_items = all_items
    self.binary_search = binary_search_perforce.BinarySearcher(
        logger_to_set=self.l)
    self.binary_search.SetSortedList(self.all_items)

  def SaveState(self):
    """Save state to STATE_FILE.

    SaveState will create a new unique, hidden state file to hold data from
    object. Then atomically overwrite the STATE_FILE symlink to point to the
    new data.

    Raises:
      Error if STATE_FILE already exists but is not a symlink.
    """
    ce, l = self.ce, self.l
    self.ce, self.l, self.binary_search.logger = None, None, None
    old_state = None

    _, path = tempfile.mkstemp(prefix=HIDDEN_STATE_FILE, dir='.')
    with open(path, 'wb') as f:
      pickle.dump(self, f)

    if os.path.exists(STATE_FILE):
      if os.path.islink(STATE_FILE):
        old_state = os.readlink(STATE_FILE)
      else:
        raise Error(('%s already exists and is not a symlink!\n'
                     'State file saved to %s' % (STATE_FILE, path)))

    # Create new link and atomically overwrite old link
    temp_link = '%s.link' % HIDDEN_STATE_FILE
    os.symlink(path, temp_link)
    os.rename(temp_link, STATE_FILE)

    if old_state:
      os.remove(old_state)

    self.ce, self.l, self.binary_search.logger = ce, l, l

  @classmethod
  def LoadState(cls):
    """Create BinarySearchState object from STATE_FILE."""
    if not os.path.isfile(STATE_FILE):
      return None
    try:
      bss = pickle.load(file(STATE_FILE))
      bss.l = logger.GetLogger()
      bss.ce = command_executer.GetCommandExecuter()
      bss.binary_search.logger = bss.l
      bss.start_time = time.time()
      bss.resumed = True
      binary_search_perforce.verbose = bss.verbose
      return bss
    except Exception:
      return None

  def RemoveState(self):
    """Remove STATE_FILE and its symlinked data from file system."""
    if os.path.exists(STATE_FILE):
      if os.path.islink(STATE_FILE):
        real_file = os.readlink(STATE_FILE)
        os.remove(real_file)
        os.remove(STATE_FILE)

  def GetNextItems(self):
    """Get next items for binary search based on result of the last test run."""
    border_item = self.binary_search.GetNext()
    index = self.all_items.index(border_item)

    next_bad_items = self.all_items[:index + 1]
    next_good_items = self.all_items[index + 1:]

    return [next_bad_items, next_good_items]

  def ElapsedTimeString(self):
    """Return h m s format of elapsed time since execution has started."""
    diff = int(time.time() - self.start_time)
    seconds = diff % 60
    minutes = (diff / 60) % 60
    hours = diff / (60 * 60)

    seconds = str(seconds).rjust(2)
    minutes = str(minutes).rjust(2)
    hours = str(hours).rjust(2)

    return '%sh %sm %ss' % (hours, minutes, seconds)

  def OutputProgress(self):
    """Output current progress of binary search to console and logs."""
    out = ('\n***** PROGRESS (elapsed time: %s) *****\n'
           'Search %d of estimated %d.\n'
           'Prune %d of max %d.\n'
           'Current bad items found:\n'
           '%s\n'
           '************************************************')
    out = out % (self.ElapsedTimeString(),
                 self.search_cycles + 1,
                 math.ceil(math.log(len(self.all_items), 2)),
                 self.prune_cycles + 1,
                 self.prune_iterations,
                 str(self.found_items))

    self.l.LogOutput(out)

  def __str__(self):
    ret = ''
    ret += 'all: %s\n' % str(self.all_items)
    ret += 'currently_good: %s\n' % str(self.currently_good_items)
    ret += 'currently_bad: %s\n' % str(self.currently_bad_items)
    ret += str(self.binary_search)
    return ret


class MockBinarySearchState(BinarySearchState):
  """Mock class for BinarySearchState."""

  def __init__(self, **kwargs):
    # Initialize all arguments to None
    default_kwargs = {
        'get_initial_items': 'echo "1"',
        'switch_to_good': None,
        'switch_to_bad': None,
        'install_script': None,
        'test_script': None,
        'incremental': True,
        'prune': False,
        'iterations': 50,
        'prune_iterations': 100,
        'verify_level': 1,
        'file_args': False,
        'verbose': False
    }
    default_kwargs.update(kwargs)
    super(MockBinarySearchState, self).__init__(**default_kwargs)


def _CanonicalizeScript(script_name):
  """Return canonical path to script.

  Args:
    script_name: Relative or absolute path to script

  Returns:
    Canonicalized script path
  """
  script_name = os.path.expanduser(script_name)
  if not script_name.startswith('/'):
    return os.path.join('.', script_name)


def Run(get_initial_items, switch_to_good, switch_to_bad, test_script,
        install_script=None, iterations=50, prune=True, noincremental=False,
        file_args=False, verify_level=1, prune_iterations=100, verbose=False,
        resume=False):
  """Run binary search tool. Equivalent to running through terminal.

  Args:
    get_initial_items: Script to enumerate all items being binary searched
    switch_to_good: Script that will take items as input and switch them to good
                    set
    switch_to_bad: Script that will take items as input and switch them to bad
                   set
    test_script: Script that will determine if the current combination of good
                 and bad items make a "good" or "bad" result.
    install_script: Script to do necessary setup (building, compilation, etc.)
                    for test_script
    iterations: How many binary search iterations to run before exiting.
    prune: If False the binary search tool will stop when the first bad item is
           found. Otherwise then binary search tool will continue searching
           until all bad items are found (or prune_iterations is reached).
    noincremental: Whether to send "diffs" of good/bad items to switch scripts.
    file_args: If True then arguments to switch scripts will be a file name
               containing a newline separated list of the items to switch.
    verify_level: How many verification tests to run to ensure initial good/bad
                  sets actually produce a good/bad result.
    prune_iterations: Max number of bad items to search for.
    verbose: If True will print extra debug information to user.
    resume: If True will resume using STATE_FILE.

  Returns:
    0 for success, error otherwise
  """
  if resume:
    bss = BinarySearchState.LoadState()
    if not bss:
      logger.GetLogger().LogOutput(
          '%s is not a valid binary_search_tool state file, cannot resume!' %
          STATE_FILE)
      return 1
  else:
    switch_to_good = _CanonicalizeScript(switch_to_good)
    switch_to_bad = _CanonicalizeScript(switch_to_bad)
    if install_script:
      install_script = _CanonicalizeScript(install_script)
    test_script = _CanonicalizeScript(test_script)
    get_initial_items = _CanonicalizeScript(get_initial_items)
    incremental = not noincremental

    binary_search_perforce.verbose = verbose

    bss = BinarySearchState(get_initial_items, switch_to_good, switch_to_bad,
                            install_script, test_script, incremental, prune,
                            iterations, prune_iterations, verify_level,
                            file_args, verbose)
    bss.DoVerify()

  try:
    bss.DoSearch()
    bss.RemoveState()
    logger.GetLogger().LogOutput('Total execution time: %s' %
                                 bss.ElapsedTimeString())
  except Error as e:
    logger.GetLogger().LogError(e)
    return 1

  return 0


def Main(argv):
  """The main function."""
  # Common initializations

  parser = argparse.ArgumentParser()
  common.BuildArgParser(parser)
  logger.GetLogger().LogOutput(' '.join(argv))
  options = parser.parse_args(argv)

  if not (options.get_initial_items and options.switch_to_good and
          options.switch_to_bad and options.test_script) and not options.resume:
    parser.print_help()
    return 1

  if options.resume:
    logger.GetLogger().LogOutput('Resuming from %s' % STATE_FILE)
    if len(argv) > 1:
      logger.GetLogger().LogOutput(('Note: resuming from previous state, '
                                    'ignoring given options and loading saved '
                                    'options instead.'))

  # Get dictionary of all options
  args = vars(options)
  return Run(**args)


if __name__ == '__main__':
  sys.exit(Main(sys.argv[1:]))
