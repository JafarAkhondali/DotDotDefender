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
LOCK_FILENAME = "/tmp/0d-poc-local.running"


def pick_lock():
    os.remove(LOCK_FILENAME)


def conv_url_to_path(url):
    return f"/usr/src/app{gh_url_to_path(url)}"


def main():
    proj_id, proj_name, proj_filename, github_url = db.fetch_project_at_step_with_pause_reason(STEP_SEMGREPED,
                                                                                               PAUSED_POC_NOT_VULNERABLE_NETWORK)
    if not proj_id:
        print("No new projects to check")
        return
    execPath = conv_url_to_path(github_url)
    githubLink = f"https://github.com/{proj_name}"
    appId = "".join(random.choices(string.hexdigits, k=8))
    print(proj_name, proj_filename, execPath)
    result = subprocess.run(
        f"timeout 600 bash ./run-local.sh {githubLink} {execPath} {appId}", shell=True, text=True
    )

    # with open('run_method.txt') as run_method_file:
    #     run_method = run_method_file.read()
    # assert run_method in ['node', 'yarn_start', 'node_installed']

    # Get the output (stdout and stderr)

    # output = result.stdout + result.stderr
    # print(output)
    # Get the exit code
    exit_code = result.returncode

    if exit_code != 0:
        db.pause_project(proj_id, PAUSED_POC_NOT_VULNERABLE_LOCAL)
        return
    db.set_is_local_flag_and_unpause(proj_id)
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
