# Copyright (c) 2013 The ChromiumOS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""The framework stage that produces the next generation of tasks to run.

Part of the Chrome build flags optimization.
"""

__author__ = "yuhenglong@google.com (Yuheng Long)"

import pipeline_process


def Steering(cache, generations, input_queue, result_queue):
    """The core method template that produces the next generation of tasks to run.

    This method waits for the results of the tasks from the previous generation.
    Upon the arrival of all these results, the method uses them to generate the
    next generation of tasks.

    The main logic of producing the next generation from previous generation is
    application specific. For example, in the genetic algorithm, a task is
    produced by combining two parents tasks, while in the hill climbing algorithm,
    a task is generated by its immediate neighbor. The method 'Next' is overridden
    in the concrete subclasses of the class Generation to produce the next
    application-specific generation. The steering method invokes the 'Next'
    method, produces the next generation and submits the tasks in this generation
    to the next stage, e.g., the build/compilation stage.

    Args:
      cache: It stores the experiments that have been conducted before. Used to
        avoid duplicate works.
      generations: The initial generations of tasks to be run.
      input_queue: The input results from the last stage of the framework. These
        results will trigger new iteration of the algorithm.
      result_queue: The output task queue for this pipeline stage. The new tasks
        generated by the steering algorithm will be sent to the next stage via
        this queue.
    """

    # Generations that have pending tasks to be executed. Pending tasks are those
    # whose results are not ready. The tasks that have their results ready are
    # referenced to as ready tasks. Once there is no pending generation, the
    # algorithm terminates.
    waiting = generations

    # Record how many initial tasks there are. If there is no task at all, the
    # algorithm can terminate right away.
    num_tasks = 0

    # Submit all the tasks in the initial generations to the next stage of the
    # framework. The next stage can be the build/compilation stage.
    for generation in generations:
        # Only send the task that has not been performed before to the next stage.
        for task in [task for task in generation.Pool() if task not in cache]:
            result_queue.put(task)
            cache.add(task)
            num_tasks += 1

    # If there is no task to be executed at all, the algorithm returns right away.
    if not num_tasks:
        # Inform the next stage that there will be no more task.
        result_queue.put(pipeline_process.POISONPILL)
        return

    # The algorithm is done if there is no pending generation. A generation is
    # pending if it has pending task.
    while waiting:
        # Busy-waiting for the next task.
        if input_queue.empty():
            continue

        # If there is a task whose result is ready from the last stage of the
        # feedback loop, there will be one less pending task.

        task = input_queue.get()

        # Store the result of this ready task. Intermediate results can be used to
        # generate report for final result or be used to reboot from a crash from
        # the failure of any module of the framework.
        task.LogSteeringCost()

        # Find out which pending generation this ready task belongs to. This pending
        # generation will have one less pending task. The "next" expression iterates
        # the generations in waiting until the first generation whose UpdateTask
        # method returns true.
        generation = next(gen for gen in waiting if gen.UpdateTask(task))

        # If there is still any pending task, do nothing.
        if not generation.Done():
            continue

        # All the tasks in the generation are finished. The generation is ready to
        # produce the next generation.
        waiting.remove(generation)

        # Check whether a generation should generate the next generation.
        # A generation may not generate the next generation, e.g., because a
        # fixpoint has been reached, there has not been any improvement for a few
        # generations or a local maxima is reached.
        if not generation.IsImproved():
            continue

        for new_generation in generation.Next(cache):
            # Make sure that each generation should contain at least one task.
            assert new_generation.Pool()
            waiting.append(new_generation)

            # Send the tasks of the new generations to the next stage for execution.
            for new_task in new_generation.Pool():
                result_queue.put(new_task)
                cache.add(new_task)

    # Steering algorithm is finished and it informs the next stage that there will
    # be no more task.
    result_queue.put(pipeline_process.POISONPILL)
