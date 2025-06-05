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
LOCK_FILENAME = "/tmp/0d-poc-dos.running"


def pick_lock():
    os.remove(LOCK_FILENAME)


def conv_url_to_path(url):
    return f"/usr/src/app{gh_url_to_path(url)}"


def main():
    proj_id, proj_name, proj_filename, github_url = db.fetch_project_at_step_with_dos_status(
        STEP_POC_SUCCESS, DOS_NOT_CHECKED
    )
    if not proj_id:
        print("No new projects to check")
        return
    execPath = conv_url_to_path(github_url)

    githubLink = f"https://github.com/{proj_name}"
    appId = "".join(random.choices(string.hexdigits, k=8))
    print(proj_name, proj_filename, execPath)
    result = subprocess.run(
        f"timeout 1200 bash ./run-dos.sh {githubLink} {execPath} {appId}", shell=True, text=True
    )

    # Get the output (stdout and stderr)

    # output = result.stdout + result.stderr
    # print(output)
    # Get the exit code
    exit_code = result.returncode

    if exit_code == 0:
        db.set_vulnerable_to_dos(proj_id, DOS_VULNERABLE)
    else:
        db.set_vulnerable_to_dos(proj_id, DOS_NOT_VULNERABLE)
    # db.change_project_step(proj_id, STEP_DOS_CHECKED)


if __name__ == "__main__":
    if os.path.isfile(LOCK_FILENAME):
        print("Already running")
        exit(0)
    open(LOCK_FILENAME, "w").close()
    atexit.register(pick_lock)

    while True:
        main()
        time.sleep(2)
