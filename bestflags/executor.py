"""The Execution stage of the framework.

Execute the image against a set of benchmarks. This stage sets up a number of
processes, calls the actual execute method and caches the results.
"""

__author__ = 'yuhenglong@google.com (Yuheng Long)'

import multiprocessing


class Tester(object):
  """Execute the generated images against a set of benchmark applications."""

  def __init__(self, numProcess, costs):
    """Set up the process pool and the results cached.

    Args:
        numProcess: Maximum number of execution to run in parallel
        costs: Executions that have been benchmarked before
    """

    self._pool = multiprocessing.Pool(numProcess)
    self._costs = costs

  def _set_cost(self, image, cost):
    """Record the execution result for the current image.

    Args:
      image: The input image for the execution
      cost: the time it takes to execute the image
    """

    pass

  def _execute(self, task):
    """Execute the benchmarks on task.

    The concrete subclass should implement the actual execution.

    Args:
      task: The input task for the execution
    """
    # raise Exception('Must be implemented in child class')
    pass

  def _execute_task(self, task):
    """Execute the input task and record the cost.

    Args:
      task: The task to be compiled
    """
    pass

  def execute(self, generation):
    """Execute the image for all entities in a generation.

    Call them in parallel in processes.

    Args:
      generation: A new generation to be executed.
    """

    self._pool.map(self._execute_task, generation.task, 1)
