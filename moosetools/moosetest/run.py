import os
import io
import sys
import copy
import time
import asyncio
import traceback
import threading
import multiprocessing
multiprocessing.set_start_method('fork')

import concurrent.futures

#import threading

#import dill

import queue
import logging
import collections

from moosetools.mooseutils import color_text
from moosetools.moosetest.base import State, TestCase
#from moosetools.moosetest.base import Runner
from moosetools.moosetest.runners import ProcessRunner
from moosetools.moosetest.differs import TextDiff
from moosetools.moosetest.formatters import SimpleFormatter


def _execute_testcase(tc, conn):
    try:
        state, results = tc.execute()
    except Exception:
        state = TestCase.Result.FATAL
        results = {tc.name(): (TestCase.Result.FATAL, 1, '', traceback.format_exc())}
    conn.send((state, results))
    conn.close()

def execute_testcases(testcases, q, timeout):

    skip_message = None

    for tc in testcases:
        unique_id = tc.getParam('_unique_id')
        if skip_message:
            state = TestCase.Result.SKIP
            results = {tc.name(): (TestCase.Result.SKIP, 0, '', skip_message)}
            q.put((unique_id, TestCase.Progress.FINISHED, time.time(), state, results))
            continue

        q.put((unique_id, TestCase.Progress.RUNNING, time.time(), None, None))

        conn_recv, conn_send = multiprocessing.Pipe(False)
        proc = multiprocessing.Process(target=_execute_testcase, args=(tc, conn_send))
        proc.start()

        if conn_recv.poll(timeout):
            state, results = conn_recv.recv()
        else:
            proc.terminate()
            state = TestCase.Result.TIMEOUT
            results = {tc.name(): (TestCase.Result.TIMEOUT, 1, '', '')}

        q.put((unique_id, TestCase.Progress.FINISHED, time.time(), state, results))

        if (state.level > 0):
            skip_message = f"Previous `TestCase` ({tc.name()}) in the group returned a non-zero state of {state}."


def _running_get_results(testcase_map, complete, result_queue, num_fail):

    try:
        unique_id, progress, t, state, results = result_queue.get_nowait()
        tc = testcase_map.get(unique_id)
        if progress == TestCase.Progress.RUNNING:
            tc = testcase_map.get(unique_id)
            tc.setProgress(progress, t)
        else:
            tc = testcase_map.pop(unique_id)
            tc.setProgress(progress, t)
            tc.setState(state)
            tc.setResult(results)
            tc.reportResult()
            complete.append(tc)

            if state.level > 1:
                num_fail += 1

            result_queue.task_done()
    except queue.Empty:
        pass


def _running_check_max_fail(testcase_map, complete, futures, num_fail, max_fail):
    if (max_fail is not None) and (num_fail > max_fail):
        for f in futures:
            f.cancel()
        for uid in list(testcase_map.keys()):
            tc = testcase_map.get(uid)
            if tc.getProgress() == tc.Progress.WAITING:
                testcase_map.pop(uid)
                tc.setProgress(TestCase.Progress.FINISHED, time.time())
                tc.setState(TestCase.Result.SKIP)
                tc.setResult({tc.name(): (TestCase.Result.SKIP, 0, '', f"Max failures of {max_fail} exceeded.")})
                tc.reportResult()
                complete.append(tc)

def _running_report_progress(testcase_map):
    for tc in testcase_map.values():
        tc.reportProgress()




def run(groups, controllers, formatter, n_threads=None, timeout=None, progress_interval=None, max_fail=None):

    start_time = time.time()

    tc_kwargs = dict()
    tc_kwargs['progress_interval'] = progress_interval
    tc_kwargs['formatter'] = formatter

    executor = concurrent.futures.ProcessPoolExecutor(max_workers=n_threads)
    manager = multiprocessing.Manager()
    result_queue = manager.Queue()

    futures = list()
    testcase_map = dict()
    for runners in groups:
        testcases = [TestCase(runner=runner, **tc_kwargs) for runner in runners]
        #execute_testcases(testcases, result_queue, timeout)
        futures.append(executor.submit(execute_testcases, testcases, result_queue, timeout))
        for tc in testcases:
            testcase_map[tc.getParam('_unique_id')] = tc

    complete = list()
    num_fail = 0
    while len(testcase_map) > 0:
        _running_get_results(testcase_map, complete, result_queue, num_fail)
        _running_check_max_fail(testcase_map, complete, futures, num_fail, max_fail)
        _running_report_progress(testcase_map)

    print(formatter.formatComplete(complete, duration=time.time() - start_time))

if __name__ == '__main__':

    logging.basicConfig()

    grp_a = [None]*2
    grp_a[0] = ProcessRunner(name='A:test/1', command=('sleep', '4'),
                          differs=(TextDiff(name='diff', text_in_stderr='sleep'),
                                   TextDiff(name='diff2', text_in_stderr='2')))
    grp_a[1] = ProcessRunner(name='A:test/2', command=('sleep', '2'))


    grp_b = [None]*3
    grp_b[0] = ProcessRunner(name='B:test/1', command=('sleep', '3'))
    grp_b[1] = ProcessRunner(name='B:test/2', command=('sleep', '5'))
    grp_b[2] = ProcessRunner(name='B:test/3', command=('sleep', '1'))


    grp_c = [None]*2
    grp_c[0] = ProcessRunner(name='C:test/1', command=('sleep', '13'))
    grp_c[1] = ProcessRunner(name='C:test/2', command=('sleep', '1'))


    groups = [grp_a, grp_b, grp_c]

    sys.exit(run(groups, None, SimpleFormatter(), n_threads=2, timeout=10, max_fail=0))
