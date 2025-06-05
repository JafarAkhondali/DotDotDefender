#!/bin/bash
if [ "$#" -ne 3 ]; then
  echo "Usage: bash $0 repo_address relative_executable_file appid"
  exit 1
fi

REPO_ADDRESS=$1
EXEC_PATH=$2
APPID=$3
POC_FILE="pocs.txt"
app_name=node-executer-network-$APPID
src_dir=webapp-network

cleanup(){
  docker rm -v -f "$app_name" > /dev/null 2>&1
  docker ps -a | grep 'node-executer-network-' | awk '{print $1}' | xargs docker rm -v -f  >/dev/null 2>&1
  #docker system prune -f > /dev/null
  rm -rf $src_dir repositorynetwork.zip
  docker image prune -f --filter "until=1h"
  docker builder prune -f --filter "until=1h"
}

cleanup


# Read PoCs from a file
if [ ! -f "$POC_FILE" ]; then
    echo "PoC file not found!"
    exit 2
fi

#git clone "$REPO_ADDRESS.git" $src_dir
echo 'Downloading repo zip'
wget -q "$REPO_ADDRESS/archive/HEAD.zip" -O repositorynetwork.zip
unzip -q -o repositorynetwork.zip -d $src_dir
mv $src_dir/*/* $src_dir
echo 'Unzipping repo done'

# Build latest customized node docker image, and install dependencies
docker build -f DockerfileNetwork -t node-executer-network:latest . -q > /dev/null

docker run -d --name "$app_name" -v $(pwd)/$src_dir:/usr/src/app/ node-executer-network sleep 600 >/dev/null




# Execute program with node
docker exec "$app_name" node "$EXEC_PATH" > /dev/null 2>&1 &

# Wait few seconds to make sure app is running
sleep 5

get_listening_port(){
  PID=$1
  PORT=$(docker exec "$app_name" lsof -i -P -n 2>/dev/null | grep LISTEN | grep "$PID" | awk '{print $9}' | sed 's/.*://')
  echo "$PORT"
}

check_vulnerability(){
  IP=$1
  PORT=$2
  POC=$3
  FLAG=$(cat flag.txt)
  response=$(docker exec "$app_name" curl -s --path-as-is "http://${IP}:${PORT}/${POC}")
  if [[ "$response" == *"$FLAG"* ]]; then
    echo "******************************************************"
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

IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$app_name")

while IFS= read -r POC; do
  check_vulnerability "$IP" "$PORT" "$POC"
done < "$POC_FILE"

echo "Not Vulnerable"
cleanup
exit 5
