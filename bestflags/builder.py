"""The Build stage of the framework.

This module defines the builder helper and the actual build worker. If there are
duplicate tasks, for example t1 and t2, needs to be built, one of them, for
example t1, will be built and the helper waits for the result of t1 and set the
results of the other task, t2 here, to be the same as that of t1. Setting the
result of t2 to be the same as t1 is referred to as resolving the result of t2.
The build worker invokes the compile method of the tasks that are not duplicate.
"""

__author__ = 'yuhenglong@google.com (Yuheng Long)'

import pipeline_process


def build_helper(done_dict, helper_queue, built_queue, result_queue):
  """Build helper.

  This method Continuously pulls duplicate tasks from the helper_queue. The
  duplicate tasks need not be compiled. This method also pulls completed tasks
  from the worker queue and let the results of the duplicate tasks be the
  same as their corresponding finished task.

  Args:
    done_dict: A dictionary of tasks that are done. The key of the dictionary is
      the optimization flags of the task. The value of the dictionary is the
      compilation results of the corresponding task.
    helper_queue: A queue of duplicate tasks whose results need to be resolved.
      This is a communication channel between the pipeline_process and this
      helper process.
    built_queue: A queue of tasks that have been built. The results of these
      tasks are needed to resolve the results of the duplicate tasks. This is
      the communication channel between the actual build workers and this helper
      process.
    result_queue: After the results of the duplicate tasks have been resolved,
      the duplicate tasks will be sent to the next stage via this queue.
  """

  # The list of duplicate tasks, the results of which need to be resolved.
  waiting_list = []

  while True:
    # Pull duplicate task from the helper queue.
    if not helper_queue.empty():
      task = helper_queue.get()

      if task == pipeline_process.POISONPILL:
        # Poison pill means no more duplicate task from the helper queue.
        break

      # The task has not been compiled before.
      assert not task.compiled()

      # The optimization flags of this task.
      flags = task.get_flags()

      # If a duplicate task come before the corresponding resolved results from
      # the built_queue, it will be put in the waiting list. If the result
      # arrives before the duplicate task, the duplicate task will be resolved
      # right away.
      if flags in done_dict:
        # This task has been encountered before and the result is available. The
        # result can be resolved right away.
        task.set_build_result(done_dict[flags])
        result_queue.put(task)
      else:
        waiting_list.append(task)

    # Check and get compiled tasks from compiled_queue.
    get_result_from_built_queue(built_queue, done_dict, waiting_list,
                                result_queue)

  # Wait to resolve the results of the remaining duplicate tasks.
  while waiting_list:
    get_result_from_built_queue(built_queue, done_dict, waiting_list,
                                result_queue)


def get_result_from_built_queue(built_queue, done_dict, waiting_list,
                                result_queue):
  """Pull results from the compiled queue and resolves duplicate tasks.

  Args:
    built_queue: A queue of tasks that have been built. The results of these
      tasks are needed to resolve the results of the duplicate tasks. This is
      the communication channel between the actual build workers and this helper
      process.
    done_dict: A dictionary of tasks that are done. The key of the dictionary is
      the optimization flags of the task. The value of the dictionary is the
      compilation results of the corresponding task.
    waiting_list: The list of duplicate tasks, the results of which need to be
      resolved.
    result_queue: After the results of the duplicate tasks have been resolved,
      the duplicate tasks will be sent to the next stage via this queue.

  This helper method tries to pull a compiled task from the compiled queue.
  If it gets a task from the queue, it resolves the results of all the relevant
  duplicate tasks in the waiting list. Relevant tasks are the tasks that have
  the same flags as the currently received results from the built_queue.
  """
  # Pull completed task from the worker queue.
  if not built_queue.empty():
    (flags, build_result) = built_queue.get()
    done_dict[flags] = build_result

    task_list = [t for t in waiting_list if t.get_flags() == flags]
    for duplicate_task in task_list:
      duplicate_task.set_build_result(build_result)
      result_queue.put(duplicate_task)
      waiting_list.remove(duplicate_task)


def build_worker(task, helper_queue, result_queue):
  """Build worker.

  This method calls the compile method of the input task and distribute the
  result to the helper and the next stage.

  Args:
    task: Input task that needs to be built.
    helper_queue: Queue that holds the completed tasks and the build results.
      This is a communication channel between the worker and the helper.
    result_queue: Queue that holds the completed tasks and the build results.
      This is a communication channel between the worker and the next stage.
  """

  # The task has not been compiled before.
  assert not task.compiled()

  task.compile()
  helper_queue.put((task.get_flags(), task.get_build_result()))
  result_queue.put(task)
