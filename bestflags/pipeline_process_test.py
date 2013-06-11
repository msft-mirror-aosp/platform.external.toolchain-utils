"""Pipeline Process unittest."""

__author__ = 'yuhenglong@google.com (Yuheng Long)'

import multiprocessing
import unittest

import pipeline_process

# Pick an integer at random.
ERROR = -334


def MockHelper(done_dict, helper_queue, work_queue, result_queue):
  """This method echos input to the output."""
  while True:
    if not helper_queue.empty():
      task = helper_queue.get()
      if task == pipeline_process.POISONPILL:
        # Poison pill means shutdown
        break

      if task in done_dict:
        # verify that it does not get duplicate "1"s in the test.
        result_queue.put(ERROR)
      else:
        result_queue.put(('helper', task.get_key(0)))


def MockWorker(task, buffer_queue, result_queue):
  result_queue.put(('worker', task.get_key(0)))


class MockTask(object):
  def __init__(self, key):
    self._key = key

  def get_key(self, stage):
    return self._key


class PipelineProcessTest(unittest.TestCase):
  """This class test the PipelineProcess.

  All the task inserted into the input queue should be taken out and hand to the
  actual pipeline handler, except for the POISON_PILL.  All these task should
  also be passed to the next pipeline stage via the output queue.
  """

  def setUp(self):
    pass

  def testRun(self):
    """Test the run method.

    Ensure that all the tasks inserted into the queue are properly handled.
    """

    manager = multiprocessing.Manager()
    inp = manager.Queue()
    output = manager.Queue()

    process = pipeline_process.PipelineProcess(2, 'testing', {}, 'test', inp,
                                               MockHelper, MockWorker, output)

    process.start()
    inp.put(MockTask(1))
    inp.put(MockTask(1))
    inp.put(MockTask(2))
    inp.put(pipeline_process.POISONPILL)
    process.join()

    # All tasks are processed once and only once.
    result = [('worker', 1), ('helper', 1), ('worker', 2),
              pipeline_process.POISONPILL]
    while result:
      task = output.get()

      # One "1"s is passed to the worker and one to the helper.
      self.assertNotEqual(task, ERROR)

      # The messages received should be exactly the same as the result.
      self.assertTrue(task in result)
      result.remove(task)


if __name__ == '__main__':
  unittest.main()
