#!/bin/bash
if [ "$#" -ne 3 ]; then
  echo "Usage: bash $0 repo_address relative_executable_file appid"
  exit 1
fi

REPO_ADDRESS=$1
EXEC_PATH=$2
APPID=$3
POC_FILE="pocs.txt"
app_name=node-executer-dos-$APPID
src_dir=webapp-dos

cleanup(){
  docker rm -v -f "$app_name" > /dev/null 2>&1
  docker ps -a | grep 'node-executer-dos-' | awk '{print $1}' | xargs docker rm -v -f  >/dev/null 2>&1
  #docker system prune -f > /dev/null
  rm -rf $src_dir repositorydos.zip
  docker image prune -f --filter "until=1h"
  docker builder prune -f --filter "until=1h"
}

cleanup
rm -rf $src_dir
rm -f repositorydos.zip


# Read PoCs from a file
if [ ! -f "$POC_FILE" ]; then
    echo "PoC file not found!"
    exit 2
fi

#git clone "$REPO_ADDRESS.git" $src_dir
echo 'Downloading repo zip'
wget -q "$REPO_ADDRESS/archive/HEAD.zip" -O repositorydos.zip
unzip -q -o repositorydos.zip -d $src_dir
mv $src_dir/*/* $src_dir
echo 'Unzipping repo done'

# Build latest customized node docker image, and install dependencies
docker build -f DockerfileDos -t node-executer-dos:latest . -q > /dev/null

docker run -v /dev/urandom:/flag.txt -d --name "$app_name" -m 1000m --oom-kill-disable=false -v $(pwd)/$src_dir:/usr/src/app/ node-executer-dos sleep 600 >/dev/null




# Execute program with node
docker exec "$app_name" node "$EXEC_PATH" > /dev/null 2>&1 &

# Wait few seconds to make sure app is running
sleep 5

get_listening_port(){
  PID=$1
  PORT=$(docker exec "$app_name" lsof -i -P -n 2>/dev/null | grep LISTEN | grep "$PID" | awk '{print $9}' | sed 's/.*://')
  echo "$PORT"
}

do_dos(){
  PORT=$1
  POC=$2
  timeout 0.5 docker exec "$app_name" curl -s --path-as-is "http://127.0.0.1:${PORT}/${POC}" >/dev/null 2>&1
}

#TODO: What if program is not running by node? Maybe save PID to file
PID=$(docker exec "$app_name" pgrep node 2>/dev/null)

if [ -z "$PID" ]; then
  #TODO: Check existence of ".lock" file, and try to use preferred package manager like yarn or npm
#  docker exec "$app_name" npm install --no-audit --progress=false > /dev/null 2>&1
  docker exec "$app_name" yarn install  > /dev/null 2>&1
  if [ -z "$PID" ]; then
    docker exec "$app_name" node "$EXEC_PATH" > /dev/null 2>&1 &
    PID=$(docker exec "$app_name" pgrep node 2>/dev/null)
    if [ -z "$PID" ]; then
      # Try to start the program with npm start
      docker exec "$app_name" "yarn" "start" > /dev/null 2>&1 &
      sleep 5
      PID=$(docker exec "$app_name" pgrep node 2>/dev/null)
      if [ -z "$PID" ]; then
        echo "PROGRAM_FAILED"
        cleanup
        exit 3
      fi
    fi
    sleep 5
  fi
fi

PORT=$(get_listening_port "$PID")
if [ -z "$PORT" ]; then
  echo "NO_PORT"
  cleanup
  exit 4
fi
sleep 3

while IFS= read -r POC; do
  do_dos "$PORT" "$POC"
done < "$POC_FILE"
sleep 10
n=$(docker exec "$app_name" ps -p $PID | wc -l)
if [ $n -eq 1 ]; then
  echo "Vulnerable"
  cleanup
  exit 0
fi
echo "Not Vulnerable"
cleanup
exit 5
