#!/bin/bash

REPO_ADDRESS=$1
EXEC_PATH=$2
APPID=$3
POC_FILE="../reporter/pocs.txt"
RUN_METHOD_FILE="run_method.txt"
app_name=node-executer-local-verify-$APPID
src_dir=webapp-local
patch_dir=$(dirname "$EXEC_PATH")

cleanup(){
  docker rm -v -f "$app_name" > /dev/null 2>&1
  docker ps -a | grep 'node-executer-local' | awk '{print $1}' | xargs docker rm -v -f  >/dev/null 2>&1
  #docker system prune -f > /dev/null
  # commented
  rm -rf $src_dir repositorylocal.zip >/dev/null 2>&1
  # NOT UNCOMMENT NEXT LINE! We need to read RUN_METHOD_FILE after script is completed.
  # rm $RUN_METHOD_FILE
  docker image prune -f --filter "until=1h" >/dev/null 2>&1
  docker builder prune -f --filter "until=1h" >/dev/null 2>&1
}

cleanup

rm $RUN_METHOD_FILE 2> /dev/null


# Read PoCs from a file
if [ ! -f "$POC_FILE" ]; then
    echo "PoC file not found!"
    cleanup
    exit 2
fi

#git clone "$REPO_ADDRESS.git" $src_dir
echo 'Downloading repo zip'
rm -rf $src_dir repositorylocal.zip >/dev/null 2>&1
wget -q "$REPO_ADDRESS/archive/HEAD.zip" -O repositorylocal.zip
unzip -q -o repositorylocal.zip -d $src_dir
mv $src_dir/*/* $src_dir
echo 'Unzipping repo done'

if [ ! -f "$(pwd)/$src_dir/${EXEC_PATH:12}" ]; then
    echo "Repo or file deleted!"
    cleanup
    exit 8
fi

# Build latest customized node docker image, and install dependencies
docker build -f DockerfileLocal -t node-executer-local-verfy:latest . -q > /dev/null

docker run -d --name "$app_name" -v $(pwd)/$src_dir:/usr/src/app/ node-executer-local-verfy sleep 600 >/dev/null

if [[ -n "$4" ]]; then
  # Patch file is available, apply it inside container
  patch_filename=$(basename "$4" .patch)
  docker cp "$4" "$app_name":"/usr/src/app/$patch_filename.patch" > /dev/null
#  docker exec $app_name patch --fuzz=3 --ignore-whitespace --verbose -t -d $patch_dir -i /usr/src/app/$patch_filename.patch
  docker exec -w "$patch_dir" $app_name patch --fuzz=3 --ignore-whitespace --verbose "$EXEC_PATH" -i /usr/src/app/$patch_filename.patch
  # In case patching failed, retry the process.
  if [ $? -ne 0 ]; then
    exit 50
  fi
  docker exec $app_name cat $EXEC_PATH
  echo "[*] Patching is done"
fi
# Execute program with node
docker exec -w "$patch_dir" "$app_name" node "$EXEC_PATH" > /dev/null 2>&1 &

# Wait few seconds to make sure app is running
sleep 8

get_listening_port(){
  PID=$1
  PORT=$(docker exec "$app_name" lsof -i -P -n 2>/dev/null | grep LISTEN | grep "$PID" | awk '{print $9}' | sed 's/.*://')
  echo "$PORT"
}

check_vulnerability(){
  PORT=$1
  POC=$2
  FLAG=$(cat flag.txt)
  response=$(docker exec "$app_name" curl -s --path-as-is "http://localhost:${PORT}/${POC}")
  if [[ "$response" == *"$FLAG"* ]]; then
    echo "Vulnerable"
    echo "$POC"
    echo -n "$POC" > payload.txt
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
  patch_dir=$(dirname "$EXEC_PATH")
  docker exec -w "$patch_dir" "$app_name" yarn install  > /dev/null 2>&1
  if [ -z "$PID" ]; then
    docker exec -w "$patch_dir" "$app_name" node "$EXEC_PATH" > /dev/null 2>&1 &
    sleep 5;
    PID=$(docker exec "$app_name" pgrep node 2>/dev/null)
    if [ -z "$PID" ]; then
      # Try to start the program with npm start
      docker exec "$app_name" "yarn" "start" > /dev/null 2>&1 &
      sleep 5

      #TODO: Maybe we should also check for other processes like deno?
      PID=$(docker exec "$app_name" pgrep node 2>/dev/null)
      if [ -z "$PID" ]; then
        echo -n "PROGRAM_FAILED"
        cleanup
        exit 3
      else
        echo -n "yarn_start" > $RUN_METHOD_FILE
      fi
    else
      echo -n "node_installed" > $RUN_METHOD_FILE
    fi
    sleep 5
  fi
else
  echo -n "node" > $RUN_METHOD_FILE
fi

PORT=$(get_listening_port "$PID")
if [ -z "$PORT" ]; then
  echo "NO_PORT"
  cleanup
  exit 4
fi

# Verify that the program is not returning 403 for normal requests
# Some apps and not configured to show response on root page, we add index.html to help mitigate it
docker exec "$app_name" bash -c "echo 'fixer' >> $patch_dir/index.html"
docker exec "$app_name" bash -c "echo 'fixer' >> /usr/src/app/index.html"

status_code=$(docker exec "$app_name" curl -s -o /dev/null -w "%{http_code}" --path-as-is "http://localhost:${PORT}/index.html")
if [[ "$status_code" == 403 ]]; then
    echo "Received a 403 response for normal request!: $status_code"
    exit 6
fi
sleep 2;

PORT=$(get_listening_port "$PID")
if [ -z "$PORT" ]; then
  echo "NO_PORT"
  cleanup
  exit 7
fi

while IFS= read -r POC; do
  check_vulnerability "$PORT" "$POC"
done < "$POC_FILE"

echo "Not Vulnerable"
#cleanup
exit 5
