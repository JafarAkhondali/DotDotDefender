#!/bin/bash
if [ "$#" -ne 3 ]; then
  echo "Usage: bash $0 repo_address relative_executable_file appid"
  exit 1
fi

REPO_ADDRESS=$1
EXEC_PATH=$2
APPID=$3
POC_FILE="pocs.txt"
RUN_METHOD_FILE="run_method.txt"
app_name=node-executer-local-$APPID
src_dir=webapp-local


cleanup(){
  docker rm -v -f "$app_name" > /dev/null 2>&1
  docker ps -a | grep 'node-executer-local' | awk '{print $1}' | xargs docker rm -v -f  >/dev/null 2>&1
  #docker system prune -f > /dev/null
  rm -rf $src_dir repositorylocal.zip
  # NOT UNCOMMENT NEXT LINE! We need to read RUN_METHOD_FILE after script is completed.
  # rm $RUN_METHOD_FILE
  docker image prune -f --filter "until=1h"
  docker builder prune -f --filter "until=1h"
}

cleanup

rm $RUN_METHOD_FILE > /dev/null


# Read PoCs from a file
if [ ! -f "$POC_FILE" ]; then
    echo "PoC file not found!"
    exit 2
fi

#git clone "$REPO_ADDRESS.git" $src_dir
echo 'Downloading repo zip'
wget -q "$REPO_ADDRESS/archive/HEAD.zip" -O repositorylocal.zip
unzip -q -o repositorylocal.zip -d $src_dir
mv $src_dir/*/* $src_dir
echo 'Unzipping repo done'

# Build latest customized node docker image, and install dependencies
docker build -f DockerfileLocal -t node-executer-local:latest . -q > /dev/null

docker run -d --name "$app_name" -v $(pwd)/$src_dir:/usr/src/app/ node-executer-local sleep 600 >/dev/null




# Execute program with node
docker exec "$app_name" node "$EXEC_PATH" > /dev/null 2>&1 &

# Wait few seconds to make sure app is running
sleep 7

get_listening_port(){
  PID=$1
  PORT=$(docker exec "$app_name" lsof -i -P -n 2>/dev/null | grep LISTEN | grep "$PID" | awk '{print $9}' | sed 's/.*://')
  #PORT=$(docker exec "$app_name" lsof -i -P -n 2>/dev/null | grep LISTEN | grep "$PID" | awk '{print $9}' | tr -d '\n')
  echo "$PORT"
}

check_vulnerability(){
  PORT=$1
  POC=$2
  FLAG=$(cat flag.txt)
  response=$(docker exec "$app_name" curl -s --path-as-is "http://localhost:${PORT}/${POC}")
  #echo $response;
  if [[ "$response" == *"$FLAG"* ]]; then
    echo "Vulnerable"
    echo "$POC"
    cleanup
    exit 0
  fi
}

#TODO: What if program is not running by node? Maybe save PID to file
PID=$(docker exec "$app_name" pgrep node 2>/dev/null)


# Welcome to spaghetti code
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

      #TODO: Maybe we should also check for other processes like deno?
      PID=$(docker exec "$app_name" pgrep node 2>/dev/null)
      if [ -z "$PID" ]; then
        echo "PROGRAM_FAILED"
        cleanup
        exit 3
      else
        echo "yarn_start" > $RUN_METHOD_FILE
      fi
    else
      echo "node_installed" > $RUN_METHOD_FILE
    fi
    sleep 5
  fi
else
  echo "node" > $RUN_METHOD_FILE
fi

PORT=$(get_listening_port "$PID")
if [ -z "$PORT" ]; then
  echo "NO_PORT"
  cleanup
  exit 4
fi

while IFS= read -r POC; do
  check_vulnerability "$PORT" "$POC"
done < "$POC_FILE"

echo "Not Vulnerable"
cleanup
exit 5
