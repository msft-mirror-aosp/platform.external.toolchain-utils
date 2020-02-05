# Copyright 2016 Googie Inc.  All rights Reserved.
#
# This script is used to help the compiler wrapper in the ChromeOS and
# Android build systems bisect for bad object files.
#
# pylint: disable=not-callable
# pylint: disable=indentation

"""Utilities for bisection of ChromeOS and Android object files.

This module contains a set of utilities to allow bisection between
two sets (good and bad) of object files. Mostly used to find compiler
bugs.

Reference page:
https://sites.google.com/a/google.com/chromeos-toolchain-team-home2/home/team-tools-and-scripts/bisecting-chromeos-compiler-problems/bisection-compiler-wrapper

Design doc:
https://docs.google.com/document/d/1yDgaUIa2O5w6dc3sSTe1ry-1ehKajTGJGQCbyn0fcEM
"""

from __future__ import print_function

import contextlib
import fcntl
import os
import shutil
import subprocess
import stat
import sys

VALID_MODES = ('POPULATE_GOOD', 'POPULATE_BAD', 'TRIAGE')
GOOD_CACHE = 'good'
BAD_CACHE = 'bad'
LIST_FILE = os.path.join(GOOD_CACHE, '_LIST')

CONTINUE_ON_MISSING = os.environ.get('BISECT_CONTINUE_ON_MISSING', None) == '1'
CONTINUE_ON_REDUNDANCY = os.environ.get('BISECT_CONTINUE_ON_REDUNDANCY',
                                        None) == '1'
WRAPPER_SAFE_MODE = os.environ.get('BISECT_WRAPPER_SAFE_MODE', None) == '1'


class Error(Exception):
  """The general compiler wrapper error class."""


@contextlib.contextmanager
def lock_file(path, mode):
  """Lock file and block if other process has lock on file.

  Acquire exclusive lock for file. Only blocks other processes if they attempt
  to also acquire lock through this method. If only reading (modes 'r' and 'rb')
  then the lock is shared (i.e. many reads can happen concurrently, but only one
  process may write at a time).

  This function is a contextmanager, meaning it's meant to be used with the
  "with" statement in Python. This is so cleanup and setup happens automatically
  and cleanly. Execution of the outer "with" statement happens at the "yield"
  statement. Execution resumes after the yield when the outer "with" statement
  ends.

  Args:
    path: path to file being locked
    mode: mode to open file with ('w', 'r', etc.)
  """
  with open(path, mode) as f:
    # Apply FD_CLOEXEC argument to fd. This ensures that the file descriptor
    # won't be leaked to any child processes.
    current_args = fcntl.fcntl(f.fileno(), fcntl.F_GETFD)
    fcntl.fcntl(f.fileno(), fcntl.F_SETFD, current_args | fcntl.FD_CLOEXEC)

    # Reads can share the lock as no race conditions exist. If write is needed,
    # give writing process exclusive access to the file.
    if f.mode == 'r' or f.mode == 'rb':
      lock_type = fcntl.LOCK_SH
    else:
      lock_type = fcntl.LOCK_EX

    try:
      fcntl.lockf(f, lock_type)
      yield f
      f.flush()
    finally:
      fcntl.lockf(f, fcntl.LOCK_UN)


def log_to_file(path, execargs, link_from=None, link_to=None):
  """Common logging function.

  Log current working directory, current execargs, and a from-to relationship
  between files.
  """
  with lock_file(path, 'a') as log:
    log.write('cd: %s; %s\n' % (os.getcwd(), ' '.join(execargs)))
    if link_from and link_to:
      log.write('%s -> %s\n' % (link_from, link_to))


def exec_and_return(execargs):
  """Execute process and return.

  Execute according to execargs and return immediately. Don't inspect
  stderr or stdout.
  """
  return subprocess.call(execargs)


def which_cache(obj_file):
  """Determine which cache an object belongs to.

  The binary search tool creates two files for each search iteration listing
  the full set of bad objects and full set of good objects. We use this to
  determine where an object file should be linked from (good or bad).
  """
  bad_set_file = os.environ.get('BISECT_BAD_SET')
  if in_object_list(obj_file, bad_set_file):
    return BAD_CACHE
  else:
    return GOOD_CACHE


def makedirs(path):
  """Try to create directories in path."""
  try:
    os.makedirs(path)
  except os.error:
    if not os.path.isdir(path):
      raise


def get_obj_path(execargs):
  """Get the object path for the object file in the list of arguments.

  Returns:
    Absolute object path from execution args (-o argument). If no object being
    outputted, then return empty string. -o argument is checked only if -c is
    also present.
  """
  try:
    i = execargs.index('-o')
    _ = execargs.index('-c')
  except ValueError:
    return ''

  obj_path = execargs[i + 1]
  # Ignore args that do not create a file.
  if obj_path in (
      '-',
      '/dev/null',
  ):
    return ''
  # Ignore files ending in .tmp.
  if obj_path.endswith(('.tmp',)):
    return ''
  # Ignore configuration files generated by Automake/Autoconf/CMake etc.
  if (obj_path.endswith('conftest.o') or
      obj_path.endswith('CMakeFiles/test.o') or
      obj_path.find('CMakeTmp') != -1 or
      os.path.abspath(obj_path).find('CMakeTmp') != -1):
    return ''

  return os.path.abspath(obj_path)


def get_dep_path(execargs):
  """Get the dep file path for the dep file in the list of arguments.

  Returns:
    Absolute path of dependency file path from execution args (-o argument). If
    no dependency being outputted then return empty string.
  """
  if '-MD' not in execargs and '-MMD' not in execargs:
    return ''

  # If -MF is given this is the path of the dependency file. Otherwise the
  # dependency file is the value of -o but with a .d extension
  if '-MF' in execargs:
    i = execargs.index('-MF')
    dep_path = execargs[i + 1]
    return os.path.abspath(dep_path)

  full_obj_path = get_obj_path(execargs)
  if not full_obj_path:
    return ''

  return full_obj_path[:-2] + '.d'


def get_dwo_path(execargs):
  """Get the dwo file path for the dwo file in the list of arguments.

  Returns:
    Absolute dwo file path from execution args (-gsplit-dwarf argument) If no
    dwo file being outputted then return empty string.
  """
  if '-gsplit-dwarf' not in execargs:
    return ''

  full_obj_path = get_obj_path(execargs)
  if not full_obj_path:
    return ''

  return full_obj_path[:-2] + '.dwo'


def in_object_list(obj_name, list_filename):
  """Check if object file name exist in file with object list."""
  if not obj_name:
    return False

  with lock_file(list_filename, 'r') as list_file:
    for line in list_file:
      if line.strip() == obj_name:
        return True

    return False


def get_side_effects(execargs):
  """Determine side effects generated by compiler

  Returns:
    List of paths of objects that the compiler generates as side effects.
  """
  side_effects = []

  # Cache dependency files
  full_dep_path = get_dep_path(execargs)
  if full_dep_path:
    side_effects.append(full_dep_path)

  # Cache dwo files
  full_dwo_path = get_dwo_path(execargs)
  if full_dwo_path:
    side_effects.append(full_dwo_path)

  return side_effects


def cache_file(execargs, bisect_dir, cache, abs_file_path):
  """Cache compiler output file (.o/.d/.dwo).

  Args:
    execargs: compiler execution arguments.
    bisect_dir: The directory where bisection caches live.
    cache: Which cache the file will be cached to (GOOD/BAD).
    abs_file_path: Absolute path to file being cached.

  Returns:
    True if caching was successful, False otherwise.
  """
  # os.path.join fails with absolute paths, use + instead
  bisect_path = os.path.join(bisect_dir, cache) + abs_file_path
  bisect_path_dir = os.path.dirname(bisect_path)
  makedirs(bisect_path_dir)
  pop_log = os.path.join(bisect_dir, cache, '_POPULATE_LOG')
  log_to_file(pop_log, execargs, abs_file_path, bisect_path)

  try:
    if os.path.exists(abs_file_path):
      if os.path.exists(bisect_path):
        # File exists
        population_dir = os.path.join(bisect_dir, cache)
        with lock_file(os.path.join(population_dir, '_DUPS'),
                       'a') as dup_object_list:
          dup_object_list.write('%s\n' % abs_file_path)
        if CONTINUE_ON_REDUNDANCY:
          return True
        raise Exception(
            'Trying to cache file %s multiple times. To avoid the error, set \
            CONTINUE_ON_REDUNDANCY to 1. For reference, the list of such files \
            will be written to %s' % (abs_file_path,
                                      os.path.join(population_dir, '_DUPS')))

      shutil.copy2(abs_file_path, bisect_path)
      # Set cache object to be read-only so later compilations can't
      # accidentally overwrite it.
      os.chmod(bisect_path, 0o444)
      return True
    else:
      # File not found (happens when compilation fails but error code is still 0)
      return False
  except Exception:
    print('Could not cache file %s' % abs_file_path, file=sys.stderr)
    raise


def restore_file(bisect_dir, cache, abs_file_path):
  """Restore file from cache (.o/.d/.dwo).

  Args:
    bisect_dir: The directory where bisection caches live.
    cache: Which cache the file will be restored from (GOOD/BAD).
    abs_file_path: Absolute path to file being restored.
  """
  # os.path.join fails with absolute paths, use + instead
  cached_path = os.path.join(bisect_dir, cache) + abs_file_path
  if os.path.exists(cached_path):
    if os.path.exists(abs_file_path):
      os.remove(abs_file_path)
    shutil.copy2(cached_path, abs_file_path)
    # Add write permission to the restored object files as some packages
    # (such as kernels) may need write permission to delete files.
    os.chmod(abs_file_path, os.stat(abs_file_path).st_mode | stat.S_IWUSR)
  else:
    raise Error(('%s is missing from %s cache! Unsure how to proceed. Make '
                 'will now crash.' % (cache, cached_path)))


def bisect_populate(execargs, bisect_dir, population_name):
  """Add necessary information to the bisect cache for the given execution.

  Extract the necessary information for bisection from the compiler
  execution arguments and put it into the bisection cache. This
  includes copying the created object file, adding the object
  file path to the cache list and keeping a log of the execution.

  Args:
    execargs: compiler execution arguments.
    bisect_dir: bisection directory.
    population_name: name of the cache being populated (good/bad).
  """
  retval = exec_and_return(execargs)
  if retval:
    return retval

  full_obj_path = get_obj_path(execargs)
  # This is not a normal compiler call because it doesn't have a -o argument,
  # or the -o argument has an unusable output file.
  # It's likely that this compiler call was actually made to invoke the linker,
  # or as part of a configuratoin test. In this case we want to simply call the
  # compiler and return.
  if not full_obj_path:
    return retval

  # Return if not able to cache the object file
  if not cache_file(execargs, bisect_dir, population_name, full_obj_path):
    return retval

  population_dir = os.path.join(bisect_dir, population_name)
  with lock_file(os.path.join(population_dir, '_LIST'), 'a') as object_list:
    object_list.write('%s\n' % full_obj_path)

  for side_effect in get_side_effects(execargs):
    _ = cache_file(execargs, bisect_dir, population_name, side_effect)

  return retval


def bisect_triage(execargs, bisect_dir):
  """Use object object file from appropriate cache (good/bad).

  Given a populated bisection directory, use the object file saved
  into one of the caches (good/bad) according to what is specified
  in the good/bad sets. The good/bad sets are generated by the
  high level binary search tool. Additionally restore any possible
  side effects of compiler.

  Args:
    execargs: compiler execution arguments.
    bisect_dir: populated bisection directory.
  """
  full_obj_path = get_obj_path(execargs)
  obj_list = os.path.join(bisect_dir, LIST_FILE)

  # If the output isn't an object file just call compiler
  if not full_obj_path:
    return exec_and_return(execargs)

  # If this isn't a bisected object just call compiler
  # This shouldn't happen!
  if not in_object_list(full_obj_path, obj_list):
    if CONTINUE_ON_MISSING:
      log_file = os.path.join(bisect_dir, '_MISSING_CACHED_OBJ_LOG')
      log_to_file(log_file, execargs, '? compiler', full_obj_path)
      return exec_and_return(execargs)
    else:
      raise Error(('%s is missing from cache! To ignore export '
                   'BISECT_CONTINUE_ON_MISSING=1. See documentation for more '
                   'details on this option.' % full_obj_path))

  cache = which_cache(full_obj_path)

  # If using safe WRAPPER_SAFE_MODE option call compiler and overwrite the
  # result from the good/bad cache. This option is safe and covers all compiler
  # side effects, but is very slow!
  if WRAPPER_SAFE_MODE:
    retval = exec_and_return(execargs)
    if retval:
      return retval
    os.remove(full_obj_path)
    restore_file(bisect_dir, cache, full_obj_path)
    return retval

  # Generate compiler side effects. Trick Make into thinking compiler was
  # actually executed.
  for side_effect in get_side_effects(execargs):
    restore_file(bisect_dir, cache, side_effect)

  # If generated object file happened to be pruned/cleaned by Make then link it
  # over from cache again.
  if not os.path.exists(full_obj_path):
    restore_file(bisect_dir, cache, full_obj_path)

  return 0


def bisect_driver(bisect_stage, bisect_dir, execargs):
  """Call appropriate bisection stage according to value in bisect_stage."""
  if bisect_stage == 'POPULATE_GOOD':
    return bisect_populate(execargs, bisect_dir, GOOD_CACHE)
  elif bisect_stage == 'POPULATE_BAD':
    return bisect_populate(execargs, bisect_dir, BAD_CACHE)
  elif bisect_stage == 'TRIAGE':
    return bisect_triage(execargs, bisect_dir)
  else:
    raise ValueError('wrong value for BISECT_STAGE: %s' % bisect_stage)
