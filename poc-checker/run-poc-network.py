import subprocess
import time
import logging
import atexit
import random
import string
import os
import utils.database as db
from utils.enums import *
from utils.tools import gh_url_to_path

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

# Load environment variables from .env file
LOCK_FILENAME = "/tmp/0d-poc.running"


def pick_lock():
    os.remove(LOCK_FILENAME)


def conv_url_to_path(url):
    return f"/usr/src/app{gh_url_to_path(url)}"


def main():
    proj_id, proj_name, proj_filename, github_url = db.fetch_project_at_step(
        STEP_SEMGREPED
    )
    if not proj_id:
        print("No new projects to check")
        return
    execPath = conv_url_to_path(github_url)
    githubLink = f"https://github.com/{proj_name}"
    appId = "".join(random.choices(string.hexdigits, k=8))
    print(proj_name, proj_filename, execPath)
    result = subprocess.run(
        f"timeout 600 bash ./run-network.sh {githubLink} {execPath} {appId}", shell=True, text=True
    )

    exit_code = result.returncode

    if exit_code != 0:
        exit_code_reason_mapper = {
            3: 5,  # NPM_RUN_START_FAILED
            4: 6,  # 'NO_OPEN_PORTS',
            5: 7,  # 'NOT_VULNERABLE_NETWORK',
        }
        db.pause_project(proj_id, exit_code_reason_mapper.get(exit_code))
        return
    db.change_project_step(proj_id, STEP_POC_SUCCESS)


if __name__ == "__main__":
    if os.path.isfile(LOCK_FILENAME):
        print("Already running")
        exit(0)
    open(LOCK_FILENAME, "w").close()
    atexit.register(pick_lock)

    while True:
        main()
        time.sleep(2)
