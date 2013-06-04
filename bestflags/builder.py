"""The Build stage of the framework.

Build the image according to the flag set. This stage sets up a number of
processes, calls the actual build method and caches the results.
"""

__author__ = 'yuhenglong@google.com (Yuheng Long)'

import multiprocessing


class Builder(object):
  """Compiling the source code to generate images using multiple processes."""

  def __init__(self, numProcess, images):
    """Set up the process pool and the images cached.

    Args:
      numProcess: Maximum number of builds to run in parallel
      images: Images that have been generated before
    """
    if numProcess <= 0:
      numProcess = 1
    self._pool = multiprocessing.Pool(numProcess)
    self._images = images

  def _set_cost(self, flag_set, image, cost):
    """Record the build result for the current flag_set.

    Args:
      flag_set: The optimization combination
      image: The result image for the build
      cost: the time it takes to build the image
    """

    pass

  def _build_task(self, task):
    """Compile the task and generate output.

    This stage includes compiling the input task, generating an image for the
    task and computing the checksum for the image.

    Args:
      task: The task to be compiled
    """

    pass

  def build(self, generation):
    """Build the images for all entities in a generation.

    Call them in parallel in processes.

    Args:
      generation: A new generation to be built.
    """

    self._pool.map(self._build_task, generation.task, 1)
