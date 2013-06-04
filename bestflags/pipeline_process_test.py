"""Pipeline Process unittest."""

__author__ = 'yuhenglong@google.com (Yuheng Long)'

import unittest

import pipeline_process


class PipelineProcessTest(unittest.TestCase):
  """This class test the PipelineProcess.

  All the task inserted into the input queue should be taken out and hand to the
  actual pipeline handler, except for the POISON_PILL.  All these task should
  also be passed to the next pipeline stage via the output queue.
  """

  def setUp(self):
    pass

  def testRun(self):
    """"Test the run method.

    Ensure that all the tasks inserted into the queue are properly handled.
    """
    pass

if __name__ == '__main__':
  unittest.main()
