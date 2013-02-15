#!/bin/bash
PID=$(ps ax | grep server.py | grep -v grep | cut -d' ' -f 2)
if ! [[ -z $PID ]]; then
  kill $PID
  sleep 5
  kill -9 $PID
fi
cd ~/perforce2/gcctools/chromeos/v14
g4 sync ...
cd automation/server
export PYTHONPATH=../..:$PYTHONPATH
(nohup python2.6 server.py -m test_pool.csv &) </dev/null 1>/dev/null 2>/dev/null </dev/null
