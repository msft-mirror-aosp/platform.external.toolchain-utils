become mobiletc-prebuild@chrome-dev1.hot <<EOF
PID=$(ps ax | grep server.py | grep -v grep | cut -d' ' -f 2)
###if ! [[ -z $PID ]]; then
  kill $PID
  sleep 5
  kill -9 $PID
###fi
cd ~/perforce2/gcctools/chromeos/v14
g4 sync ...
cd automation/server
pwd
nohup python server.py -m test_pool.csv &
EOF
