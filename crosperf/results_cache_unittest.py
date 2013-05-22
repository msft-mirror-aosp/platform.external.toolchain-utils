#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from utils import logger

from results_cache import Result
from results_cache import ResultsCache
import mock_instance

output = """CMD (True): ./run_remote_tests.sh --remote=172.17.128.241  --board=lumpy   LibCBench
CMD (None): cd /usr/local/google/home/yunlian/gd/src/build/images/lumpy/latest/../../../../..; cros_sdk  -- ./in_chroot_cmd6X7Cxu.sh
Identity added: /tmp/run_remote_tests.PO1234567/autotest_key (/tmp/run_remote_tests.PO1234567/autotest_key)
INFO    : Using emerged autotests already installed at /build/lumpy/usr/local/autotest.

INFO    : Running the following control files 1 times:
INFO    :  * 'client/site_tests/platform_LibCBench/control'

INFO    : Running client test client/site_tests/platform_LibCBench/control
./server/autoserv -m 172.17.128.241 --ssh-port 22 -c client/site_tests/platform_LibCBench/control -r /tmp/run_remote_tests.PO1234567/platform_LibCBench --test-retry=0 --args 
ERROR:root:import statsd failed, no stats will be reported.
14:20:22 INFO | Results placed in /tmp/run_remote_tests.PO1234567/platform_LibCBench
14:20:22 INFO | Processing control file
14:20:23 INFO | Starting master ssh connection '/usr/bin/ssh -a -x -N -o ControlMaster=yes -o ControlPath=/tmp/_autotmp_VIIP67ssh-master/socket -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o ConnectTimeout=30 -o ServerAliveInterval=180 -o ServerAliveCountMax=3 -o ConnectionAttempts=4 -o Protocol=2 -l root -p 22 172.17.128.241'
14:20:23 ERROR| [stderr] Warning: Permanently added '172.17.128.241' (RSA) to the list of known hosts.
14:20:23 INFO | INFO	----	----	kernel=3.8.11	localtime=May 22 14:20:23	timestamp=1369257623	
14:20:23 INFO | Installing autotest on 172.17.128.241
14:20:23 INFO | Using installation dir /usr/local/autotest
14:20:23 WARNI| No job_repo_url for <remote host: 172.17.128.241>
14:20:23 INFO | Could not install autotest using the packaging system: No repos to install an autotest client from. Trying other methods
14:20:23 INFO | Installation of autotest completed
14:20:24 WARNI| No job_repo_url for <remote host: 172.17.128.241>
14:20:24 INFO | Executing /usr/local/autotest/bin/autotest /usr/local/autotest/control phase 0
14:20:24 INFO | Entered autotestd_monitor.
14:20:24 INFO | Finished launching tail subprocesses.
14:20:24 INFO | Finished waiting on autotestd to start.
14:20:26 INFO | START	----	----	timestamp=1369257625	localtime=May 22 14:20:25	
14:20:26 INFO | 	START	platform_LibCBench	platform_LibCBench	timestamp=1369257625	localtime=May 22 14:20:25	
14:20:30 INFO | 		GOOD	platform_LibCBench	platform_LibCBench	timestamp=1369257630	localtime=May 22 14:20:30	completed successfully
14:20:30 INFO | 	END GOOD	platform_LibCBench	platform_LibCBench	timestamp=1369257630	localtime=May 22 14:20:30	
14:20:31 INFO | END GOOD	----	----	timestamp=1369257630	localtime=May 22 14:20:30	
14:20:31 INFO | Got lock of exit_code_file.
14:20:31 INFO | Released lock of exit_code_file and closed it.
OUTPUT: ==============================
OUTPUT: Current time: 2013-05-22 14:20:32.818831 Elapsed: 0:01:30 ETA: Unknown
Done: 0% [                                                  ]
OUTPUT: Thread Status:
RUNNING:  1 ('ttt: LibCBench (1)' 0:01:21)
Machine Status:
Machine                        Thread     Lock Status                    Checksum                        
172.17.128.241                 ttt: LibCBench (1) True RUNNING                   3ba9f2ecbb222f20887daea5583d86ba

OUTPUT: ==============================
14:20:33 INFO | Killing child processes.
14:20:33 INFO | Client complete
14:20:33 INFO | Finished processing control file
14:20:33 INFO | Starting master ssh connection '/usr/bin/ssh -a -x -N -o ControlMaster=yes -o ControlPath=/tmp/_autotmp_aVJUgmssh-master/socket -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o ConnectTimeout=30 -o ServerAliveInterval=180 -o ServerAliveCountMax=3 -o ConnectionAttempts=4 -o Protocol=2 -l root -p 22 172.17.128.241'
14:20:33 ERROR| [stderr] Warning: Permanently added '172.17.128.241' (RSA) to the list of known hosts.

INFO    : Test results:
-------------------------------------------------------------------
platform_LibCBench                                      [  PASSED  ]
platform_LibCBench/platform_LibCBench                   [  PASSED  ]
platform_LibCBench/platform_LibCBench                     b_malloc_big1__0_                                     0.00375231466667
platform_LibCBench/platform_LibCBench                     b_malloc_big2__0_                                     0.002951359
platform_LibCBench/platform_LibCBench                     b_malloc_bubble__0_                                   0.015066374
platform_LibCBench/platform_LibCBench                     b_malloc_sparse__0_                                   0.015053784
platform_LibCBench/platform_LibCBench                     b_malloc_thread_local__0_                             0.01138439
platform_LibCBench/platform_LibCBench                     b_malloc_thread_stress__0_                            0.0367894733333
platform_LibCBench/platform_LibCBench                     b_malloc_tiny1__0_                                    0.000768474333333
platform_LibCBench/platform_LibCBench                     b_malloc_tiny2__0_                                    0.000581407333333
platform_LibCBench/platform_LibCBench                     b_pthread_create_serial1__0_                          0.0291785246667
platform_LibCBench/platform_LibCBench                     b_pthread_createjoin_serial1__0_                      0.031907936
platform_LibCBench/platform_LibCBench                     b_pthread_createjoin_serial2__0_                      0.043485347
platform_LibCBench/platform_LibCBench                     b_pthread_uselesslock__0_                             0.0294113346667
platform_LibCBench/platform_LibCBench                     b_regex_compile____a_b_c__d_b__                       0.00529833933333
platform_LibCBench/platform_LibCBench                     b_regex_search____a_b_c__d_b__                        0.00165455066667
platform_LibCBench/platform_LibCBench                     b_regex_search___a_25_b__                             0.0496191923333
platform_LibCBench/platform_LibCBench                     b_stdio_putcgetc__0_                                  0.100005711667
platform_LibCBench/platform_LibCBench                     b_stdio_putcgetc_unlocked__0_                         0.0371443833333
platform_LibCBench/platform_LibCBench                     b_string_memset__0_                                   0.00275405066667
platform_LibCBench/platform_LibCBench                     b_string_strchr__0_                                   0.00456903
platform_LibCBench/platform_LibCBench                     b_string_strlen__0_                                   0.044893587
platform_LibCBench/platform_LibCBench                     b_string_strstr___aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaac__ 0.118360778
platform_LibCBench/platform_LibCBench                     b_string_strstr___aaaaaaaaaaaaaaaaaaaaaaaaac__        0.068957325
platform_LibCBench/platform_LibCBench                     b_string_strstr___aaaaaaaaaaaaaacccccccccccc__        0.0135694476667
platform_LibCBench/platform_LibCBench                     b_string_strstr___abcdefghijklmnopqrstuvwxyz__        0.0134553343333
platform_LibCBench/platform_LibCBench                     b_string_strstr___azbycxdwevfugthsirjqkplomn__        0.0133123556667
platform_LibCBench/platform_LibCBench                     b_utf8_bigbuf__0_                                     0.0473772253333
platform_LibCBench/platform_LibCBench                     b_utf8_onebyone__0_                                   0.130938538333
-------------------------------------------------------------------
Total PASS: 2/2 (100%)

INFO    : Elapsed time: 0m16s 
"""

error = """
ERROR: Identity added: /tmp/run_remote_tests.Z4Ld/autotest_key (/tmp/run_remote_tests.Z4Ld/autotest_key)
INFO    : Using emerged autotests already installed at /build/lumpy/usr/local/autotest.
INFO    : Running the following control files 1 times:
INFO    :  * 'client/site_tests/platform_LibCBench/control'
INFO    : Running client test client/site_tests/platform_LibCBench/control
INFO    : Test results:
INFO    : Elapsed time: 0m18s
"""


keyvals = {'': 'PASS', 'b_stdio_putcgetc__0_': '0.100005711667', 'b_string_strstr___azbycxdwevfugthsirjqkplomn__': '0.0133123556667', 'b_malloc_thread_local__0_': '0.01138439', 'b_string_strlen__0_': '0.044893587', 'b_malloc_sparse__0_': '0.015053784', 'b_string_memset__0_': '0.00275405066667', 'platform_LibCBench': 'PASS', 'b_pthread_uselesslock__0_': '0.0294113346667', 'b_string_strchr__0_': '0.00456903', 'b_pthread_create_serial1__0_': '0.0291785246667', 'b_string_strstr___aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaac__': '0.118360778', 'b_string_strstr___aaaaaaaaaaaaaacccccccccccc__': '0.0135694476667', 'b_pthread_createjoin_serial1__0_': '0.031907936', 'b_malloc_thread_stress__0_': '0.0367894733333', 'b_regex_search____a_b_c__d_b__': '0.00165455066667', 'b_malloc_bubble__0_': '0.015066374', 'b_malloc_big2__0_': '0.002951359', 'b_stdio_putcgetc_unlocked__0_': '0.0371443833333', 'b_pthread_createjoin_serial2__0_': '0.043485347', 'b_regex_search___a_25_b__': '0.0496191923333', 'b_utf8_bigbuf__0_': '0.0473772253333', 'b_malloc_big1__0_': '0.00375231466667', 'b_regex_compile____a_b_c__d_b__': '0.00529833933333', 'b_string_strstr___aaaaaaaaaaaaaaaaaaaaaaaaac__': '0.068957325', 'b_malloc_tiny2__0_': '0.000581407333333', 'b_utf8_onebyone__0_': '0.130938538333', 'b_malloc_tiny1__0_': '0.000768474333333', 'b_string_strstr___abcdefghijklmnopqrstuvwxyz__': '0.0134553343333'}

class MockResult(Result):

  def __init__(self, chromeos_root, logger, label_name):
    super(MockResult, self).__init__(chromeos_root, logger, label_name)

  def _FindFilesInResultsDir(self, find_args):
    return ""

  def _GetKeyvals(self):
    return keyvals


class ResultTest(unittest.TestCase):
  def testCreateFromRun(self):
    result = MockResult.CreateFromRun(logger.GetLogger(), "/tmp", "lumpy",
                                  "test1", output, error, 0)
    self.assertEqual(result.keyvals, keyvals)
    self.assertEqual(result.chroot_results_dir, "/tmp/run_remote_tests.PO1234567/platform_LibCBench")
    self.assertEqual(result.results_dir, "/tmp/chroot/tmp/run_remote_tests.PO1234567/platform_LibCBench")
    self.assertEqual(result.retval, 0)

if __name__ == "__main__":
  unittest.main()
