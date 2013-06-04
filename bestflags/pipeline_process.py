"""Pipeline process that encapsulates the actual content.

The actual stages include the Steering algorithm, the builder and the executor.
"""

__author__ = 'yuhenglong@google.com (Yuheng Long)'

import multiprocessing


class PipelineProcess(multiprocessing.Process):
  """A process that encapsulates the actual content.

  It continuously pull tasks from the queue until a poison pill is received.
  Once a job is received, it will hand it to the actual stage for processing.
  """

  # Poison pill means shutdown
  POISON_PILL = None

  def __init__(self, method, task_queue, result_queue):
    """Set up input/output queue and the actual method to be called.

    Args:
      method: The actual pipeline stage to be invoked.
      task_queue: The input task queue for this pipeline stage.
      result_queue: The output task queue for this pipeline stage.
    """

    multiprocessing.Process.__init__(self)
    self._method = method
    self._task_queue = task_queue
    self._result_queue = result_queue

  def run(self):
    """Busy pulling the next task from the queue for execution.

    Once a job is pulled, this stage invokes the actual stage method and submits
    the result to the next pipeline stage.

    The process will terminate on receiving the poison pill from previous stage.
    """

    while True:
      next_task = self.task_queue.get()
      if next_task is None:
        # Poison pill means shutdown
        self.result_queue.put(None)
        break
      self._method(next_task)
      self.result_queue.put(next_task)
