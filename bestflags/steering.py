"""A Genetic Algorithm implementation for selecting good flags."""

__author__ = 'yuhenglong@google.com (Yuheng Long)'


class Steering(object):
  """The steering algorithm that produce the next generation to be run."""

  def __init__(self, steps):
    """Set up the number of steps generations this algorithm should evolve.

    Args:
      steps: number of steps that the feed back loop should perform
    """

    self._steps = steps

  def run(self, generation):
    """Generate a set of new generations for the next round of execution.

    Args:
      generation: the previous generation.
    """

    pass
