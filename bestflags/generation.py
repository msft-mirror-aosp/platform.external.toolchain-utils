"""A generation of a set of tasks.

Part of the Chrome build flags optimization.

This module contains the core algorithm of producing the next generation of
execution.
"""

__author__ = 'yuhenglong@google.com (Yuheng Long)'


class Generation(object):
  """A generation of a framework run.

  This also contains the core implementation, reproducing new generations.
  """

  def __init__(self, pool):
    """Set up the tasks set of this generation.

    Args:
        pool: a set of tasks to be run
    """
    self._pool = pool

  def next(self):
    """Calculate the next generation.

    This is the core of the framework implementation.

    Returns:
      A new generation.
    """

  def pool(self):
    """Return the task set of this generation."""
    pass

  def improve(self):
    """True if this generation has improvement over its parent generation."""
    pass

  def get_best(self):
    """Get the best flagset."""
    return self._pool[0]
