import time
import dotenv
import logging
import os
import atexit
import json
import requests
from utils.database import *
from utils.enums import *
from utils.tools import runcommand

dotenv.load_dotenv("../.env")
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
DL_FILE_PATH = '/tmp/newscan.js'
timeCounter = 0
SEMGREP_CMD = """
timeout 30 semgrep --config="r/javascript.lang.security.audit.path-traversal.path-join-resolve-traversal.path-join-resolve-traversal" --metrics=off --output /tmp/out.json --json $FILE 2>/dev/null >/dev/null
""".strip()
LOCK_FILENAME = "/tmp/0d-grep.running"

def timing_start():
    global timeCounter
    timeCounter = int(time.time() * 1000)

def timing_finish():
    return int(time.time() * 1000) - timeCounter

def pick_lock():
    os.remove(LOCK_FILENAME)

def main():
    while True:
        proj_id, proj_filename, _, file_github_url = fetch_project_at_step(STEP_CLONED)

        if proj_id is None or file_github_url is None:
            print("[*] Waiting for new projects ...")
            time.sleep(5)
            continue
        change_project_step(proj_id, STEP_SEMGREPING)
        timing_start()

        with open(DL_FILE_PATH, 'wb') as f:
            f.write(requests.get(file_github_url).content)
        exit_code, out, err = runcommand(SEMGREP_CMD.replace("$FILE", DL_FILE_PATH))

        logging.info(out)
        if err != "":
            logging.error(err)
        add_timing_to_project(proj_id, "semgrep", timing_finish())
        if exit_code == 0:
            logging.info("Semgrep ran successfully")
            f = open("/tmp/out.json")
            stuff = json.load(f)
            f.close()
            if len(stuff["results"]) > 0:
                save_semgrep_output(proj_id, json.dumps(stuff["results"]))
                logging.info(f"Semgrep found a possible vuln in {proj_id}")
            else:
                pause_project(proj_id, PAUSED_SEMGREP_NO_RESULT)
                logging.info(f"Semgrep couldn't find a vuln in {proj_id}")
        else:
            pause_project(proj_id, PAUSED_SEMGREP_FAILED)
            logging.info("Semgrep failed")
        change_project_step(proj_id, STEP_SEMGREPED)


if __name__ == "__main__":
    if os.path.isfile(LOCK_FILENAME):
        print("Already running")
        exit(0)
    open(LOCK_FILENAME, "w").close()
    atexit.register(pick_lock)

    main()
    logging.info("All projects have been checked")
