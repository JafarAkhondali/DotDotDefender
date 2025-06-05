import logging
import sys
import requests
import json
import dotenv
import subprocess
import time
import logging
import atexit
import random
import string
import os
import shutil
import re
from modules.email import extract_email
from modules.llmfix import patch_code
from utils.database import fetch_project_without_cvss, update_cvss, fetch_project_at_step
from utils.tools import gh_url_to_raw, gh_url_to_path, read_file
from modules.cvss import CVSS
from utils.enums import *

dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
LOCK_FILENAME = "/tmp/0d-cvss.running"
import utils.database as db
from utils.enums import *
from utils.tools import gh_url_to_path

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

patch_dir = 'patches'
poc_dir = 'pocs'
MAX_PATCH_TRIES = 10
if not os.path.exists(patch_dir):
    os.makedirs(patch_dir)
if not os.path.exists(poc_dir):
    os.makedirs(poc_dir)

LOCK_FILENAME = "/tmp/0d-patcher.running"
EXIT_CODE_NOT_VULNEABLE=5
EXIT_CODE_STATIC_ANALYSIS_FAILED=50

def pick_lock():
    os.remove(LOCK_FILENAME)


def conv_url_to_path(url):
    return f"/usr/src/app{gh_url_to_path(url)}"

def test_codeql(file_path):
    file_name = os.path.basename(file_path)
    if not (file_name.endswith('.js') or file_name.endswith('.ts')):
        file_name += '.ts'
    fs = ['codeql/db','codeql/code']
    for i in fs:
        if os.path.exists(i):
            shutil.rmtree(i)
    os.mkdir('codeql/code')
    with open(file_path,'rb') as fr:
        with open(f'codeql/code/{file_name}','wb') as tfile:
            tfile.write(fr.read())
    os.system('codeql database create ./codeql/db -s ./codeql/code -l javascript --overwrite >/dev/null 2>/dev/null')
    os.system('rm /tmp/codeqlout 2>/dev/null ; rm /tmp/codeqlout.txt 2>/dev/null')
    os.system('codeql query run -d ./codeql/db  ./codeql/querypack/query-only-sanitize.ql -o /tmp/codeqlout >/dev/null 2>/dev/null ; codeql bqrs info /tmp/codeqlout > /tmp/codeqlout.txt')
    with open('/tmp/codeqlout.txt') as f:
        return int(re.search(r'select has ([0-9]+) rows', f.read()).group(1))

def generate_patch(github_url):
    code = requests.get(github_url).text
    file_path_in_project = gh_url_to_path(github_url)
    file_name = os.path.basename(file_path_in_project)
    return patch_code(code, file_name) + chr(13) + chr(10)

def validate_patch(github_link, exec_path, app_id, patch_filename,initial_n):
    with open(patch_filename) as f:
        patch = f.read()

    if os.path.exists('./static-analysis-test.ts'):
        os.unlink('./static-analysis-test.ts')
    result = subprocess.run(
        f"timeout 1200 bash ./run-local.sh {github_link} {exec_path} {app_id} {patch_filename}", shell=True, text=True
    )
    exit_code = result.returncode

    if exit_code == EXIT_CODE_NOT_VULNEABLE:
        patched_n = test_codeql('./static-analysis-test.ts')
        if patched_n > initial_n:
            logging.info(f"Static analysis done. Patch is OK. {patched_n} > {initial_n}")
            return exit_code
        else:
            logging.info(f"Static analysis done. Patch failed. {patched_n} < {initial_n}")
            return EXIT_CODE_STATIC_ANALYSIS_FAILED
    return exit_code

def read_run_method():
    run_method = read_file('run_method.txt')
    assert run_method in ['node', 'node_installed', 'yarn_start']
    return run_method


def main():
    proj_id, proj_name, proj_filename, github_url = db.fetch_project_at_step(
        STEP_POC_CVSS_READY
    )
    if not proj_id:
        print("No new projects to check")
        time.sleep(5)
        return
    exec_path = conv_url_to_path(github_url)
    github_link = f"https://github.com/{proj_name}"
    app_id = "".join(random.choices(string.hexdigits, k=8))

    print(proj_name, proj_filename, exec_path)
    if os.path.exists('./static-analysis-test.ts'):
        os.unlink('./static-analysis-test.ts')
    result = subprocess.run(
        f"timeout 1200 bash ./run-local.sh {github_link} {exec_path} {app_id}", shell=True, text=True
    )
    initial_n = test_codeql('./static-analysis-test.ts')
    exit_code = result.returncode

    if exit_code != 0:
        db.set_field(proj_id, 'exit_code', exit_code)
        if exit_code == EXIT_CODE_NOT_VULNEABLE:
            db.pause_project(proj_id, PAUSED_PROJECT_WAS_FIXED)
            return
        elif(exit_code == 7):
            db.pause_project(proj_id, PAUSED_PROJECT_IS_BUGGY)
            return
        elif(exit_code == 8):
            db.pause_project(proj_id, PAUSED_VULNERABLE_CODE_DELETED)
            return

        logging.info(f"Something went wrong! Exit code: {exit_code}")
        logging.info("Project was not vulnerable in first run, or didn't run! It shouldn't happen")
        db.pause_project(proj_id, PAUSED_UNKNOWN_REASON_ISSUE)
        return

    # Extract run method
    try:
        last_run_method = read_run_method()
    except Exception as err:
        logging.error("Reading last run method failed")
        logging.error(err)
        db.pause_project(proj_id, PAUSED_UNKNOWN_REASON_ISSUE2)
        return

    last_payload = read_file('payload.txt')

    llm_try_count = db.get_field(proj_id, 'llm_try_count', 0)

    patch_filename = f'{patch_dir}/{proj_id}.patch'

    for llm_try_count in range(llm_try_count + 1, llm_try_count + MAX_PATCH_TRIES + 1):
        print(f'Current try: {llm_try_count}')
        patch = generate_patch(github_url)
        with open(patch_filename, 'w') as f:
            f.write(patch)

        logging.info(patch_filename)
        logging.info(patch)

        exit_code = validate_patch(github_link, exec_path, app_id, patch_filename, initial_n)

        db.set_field(proj_id, 'llm_try_count', llm_try_count)
        if exit_code != EXIT_CODE_NOT_VULNEABLE:
            logging.info(f"The patch failed! Project is still vulnerable(exit code: {exit_code})")
            continue

        # Extract new run method
        try:
            new_run_method = read_run_method()
        except Exception as err:
            # Patch made the program fail to execute, try a new one ..
            continue

        if last_run_method != new_run_method:
            logging.info(f"Run method is changed! Last is '{last_run_method}', new method is {new_run_method}")
            continue

        db.set_field(proj_id, 'run_method', last_run_method)
        db.set_field(proj_id, 'poc', last_payload)

        logging.info(f"******************** Patch successful **********************")
        db.change_project_step(proj_id, STEP_PATCH_READY)
        return
    # When reaches here, it means none of the patches were successful. Pause the project for further analysis
    db.pause_project(proj_id, PAUSED_PATCH_FAILED)


if __name__ == "__main__":
    if os.path.isfile(LOCK_FILENAME):
        print("Already running")
        exit(0)
    open(LOCK_FILENAME, "w").close()
    atexit.register(pick_lock)

    while True:
        main()
        logging.info("-----------------")
