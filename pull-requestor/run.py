#!/usr/bin/env python3
import logging
import base64
import json
import requests
import sys
import time
import os
import tempfile
import atexit
import subprocess
import random
import string
import shutil
import utils.database as db
from utils.tools import gh_url_to_path
from utils.enums import *

# Replace these with your own GitHub username and personal access token
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
LOCK_FILENAME = "/tmp/0d-pullrequestor.running"
ISSUE_TITLE = 'Path traversal Vulnerability'
PULL_REQUEST_TITLE = 'Fixing a Path Traversal Vulnerability'

AUTHOR_GH_NAME = os.getenv("AUTHOR_NAME")

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


def format_run_method(file_path, run_method):
    return {
        'node': f'We used node command to run the file directly: `node .{gh_url_to_path(file_path)}`',
        'node_installed': f'We installed the dependencies using `yarn install`, and then used node command to run the file `node .{gh_url_to_path(file_path)}`',
        'yarn_start': 'We installed the dependencies, and run the project using `yarn start`'
    }.get(run_method)


def format_dos(is_vuln):
    return {
        '2': '',
        '1': f"""Denial of service vulnerability:
We also verified that this vulnerability can also lead to a Denial of Service attack, as it first loads the whole file content into memory, then tries to send the response.
Loading a large file (for example reading /dev/urandom/) can use all the memory within a few seconds and crash the server.""",
    }.get(str(is_vuln))


def format_network(is_local):
    return {
        '0': '(N)etwork',
        '1': '(A)djacent',
    }.get(str(is_local))


def generate_report(p, issue_id):
    return f"""Hello,
It's possible that you don't use this code in production or the project is not maintained anymore, but we wanted to also increase security awareness. Also if it's only for development, securing the server increases security of the developer. Sorry if it bothers you.
Due to unsafe usage of pathname used in file reads, this project is vulnerable to Local File Inclusion vulnerability.
You can read more about this vulnerability and its side effects here: https://cwe.mitre.org/data/definitions/22.html

The vulnerable code is at .{gh_url_to_path(p['file_github_url'])} file, which you can access online via: {p['file_github_url']}
If the pathname of the URL is a relative path (e.g.: ../), the returned path can be outside the intended directory and this might lead to leakage of sensitive files.

Running the project:
{format_run_method(p['file_github_url'], p['run_method'])}

Verified proof-of-concept(poc) to read hostname file(Path traversal vulnerability):
```bash
curl --path-as-is server_address:port/{p['poc'].replace('flag.txt', 'etc/hostname')}
```

{format_dos(p['is_vulnerable_to_dos'])}

By default, running the vulnerable file opens a port in the {'localhost only' if str(p['is_local']) == '1' else 'network'} scope. Thus the Attack Vector (AV) of CVSS is: {format_network(p['is_local'])}

Impact:
We've calculated the base score of the vulnerability (as proposal) as {p['base_score']:,.2}, with a severity of "{p['severity']}" using following the following vector_string: {p['vector_string']}
You can view the CVSS score online via: https://www.first.org/cvss/calculator/3.1#{p['vector_string']}

This patch is generated with the help of LLMs, we verified it's working and doesn't break application functionality but still we HIGHLY recommend you verify that it correctly mitigates the bug and doesn't hurt the functionality of your software.

{("resolve #"+str(issue_id)) if issue_id else ""}
"""


def conv_url_to_path(url):
    return f"/usr/src/app{gh_url_to_path(url)}"


def conv_url_to_gh_path(url):
    return f"{gh_url_to_path(url)}"


def get_default_branch(repo_name):
    url = f"https://api.github.com/repos/{repo_name}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        repo_info = response.json()
        return repo_info['default_branch']
    else:
        print(f"Failed to get repository information: {response.status_code}")
        print(response.json())
        return None


def is_still_vulnerable(proj, fork_url):
    proj_name = proj['project_name']
    proj_filename = proj['downloaded_file_name']
    github_url = proj['file_github_url']

    exec_path = conv_url_to_path(github_url)
    github_link = f"https://github.com/{proj_name}"
    app_id = "".join(random.choices(string.hexdigits, k=8))

    logging.info(f'Verifying name: {proj_name}, filename: {proj_filename}, execpath: {exec_path}')
    result = subprocess.run(
        f"bash ./run-local-verify.sh {github_link} {exec_path} {app_id}", shell=True, text=True
    )
    exit_code = result.returncode
    return exit_code



def failed_pullreq(project_id, pause_id, reason):
    logging.fatal("ERROR 15:"+reason)
    db.pause_project(project_id, pause_id)


def is_patch_correct(proj):
    proj_name = proj['project_name']
    proj_filename = proj['downloaded_file_name']
    github_url = proj['file_github_url']

    exec_path = conv_url_to_path(github_url)
    github_link = f"https://github.com/{proj_name}"
    app_id = "".join(random.choices(string.hexdigits, k=8))

    logging.info(f'Verifying name: {proj_name}, filename: {proj_filename}, execpath: {exec_path}')
    result = subprocess.run(
        f"bash ./run-local-verify.sh {github_link} {exec_path} {app_id} ../reporter/patches/{proj['id']}.patch",
        shell=True, text=True
    )
    exit_code = result.returncode
    return exit_code


def upload_file_to_project(fork_name, file_path, file_content):
    r = requests.get(f'https://api.github.com/repos/{fork_name}/contents{file_path}', headers={
        "Authorization": f"token {GITHUB_TOKEN}",
    })
    if r.status_code != 200:
        logging.fatal('Failed getting sha of the file being updated from GH API')
        return False
    r = r.json()
    r = requests.put(f'https://api.github.com/repos/{fork_name}/contents{file_path}', headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }, data=json.dumps({
        'message': 'Block malicious looking requests to prevent path traversal attacks.',
        'committer': {
            'name': 'Jafar Akhondali',
            'email': 'jafar.akhoondali@gmail.com'
        },
        'sha': r['sha'],
        'content': base64.b64encode(file_content).decode()
    }))

    if r.status_code != 200:
        logging.fatal('Failed updating the vulnerable code with GH API')
        return False
    return True


def check_already_sent_pull_request(repo_name):
    r = requests.get(
        f'https://api.github.com/search/issues?per_page=1&q=is:pr author:{AUTHOR_GH_NAME} repo:{repo_name} {PULL_REQUEST_TITLE}', headers={
            'Authorization': f'Token {GITHUB_TOKEN}'
        })
    if r.status_code != 200:
        return -1
    r = r.json()
    return r['total_count']


def check_already_opened_an_issue(repo_name):
    r = requests.get(
        f'https://api.github.com/search/issues?per_page=1&q=is:issue author:{AUTHOR_GH_NAME} repo:{repo_name}',
        headers={
            'Authorization': f'Token {GITHUB_TOKEN}'
        })
    if r.status_code != 200: return -1
    r = r.json()
    if 'total_count' not in r or r['total_count'] == 0: return -2
    return r


def send_pull_req(proj):
    github_repo = proj
    repo_name = proj['project_name']
    issues_url = f'https://api.github.com/repos/{repo_name}/issues'
    fork_url = f'https://api.github.com/repos/{repo_name}/forks'
    fork_name = f'{repo_name}-securityfix-{random.randint(1e5, 1e6)}'
    issue_id = None

    logging.info(f'Checking if we have already sent a report to {repo_name}...')
    already_sent = check_already_sent_pull_request(repo_name)
    if already_sent == -1:
        failed_pullreq(proj['id'], PAUSED_UNKNOWN_ERROR_GHAPI, 'Failed to get the latest issues from GH')
        return
    elif already_sent != 0:
        failed_pullreq(proj['id'], PAUSED_VULN_ALREADY_REPORTER, f'Already reported to {repo_name}!')
        return
    already_sent = check_already_opened_an_issue(repo_name)
    #print(already_sent)
    if False and already_sent == -1: # We don't have to pause projects that don't have list of issues.
        failed_pullreq(proj['id'], PAUSED_UNKNOWN_ERROR_GHAPI, f'Failed to get the latest issues from GH')
        return
    elif already_sent != -2:
        #failed_pullreq(proj['id'], PAUSED_VULN_ALREADY_REPORTER, 'Already reported!')
        issue_id = already_sent['items'][0]['number']
        print(f"Found issue id: {issue_id}")
        #return
    logging.info(f'Preparing to send pull request to "{repo_name}"!')
    logging.info(f'Checking if "{repo_name}" is still vulnerable...')
    # Fork the project!!
    response = requests.post(fork_url, headers={"Authorization": f"token {GITHUB_TOKEN}"}, json={'name': fork_name})

    if response.status_code == 202:
        logging.info('Successfully forked the repo!')
    else:
        failed_pullreq(proj['id'], PAUSED_UNKNOWN_ERROR_GHAPI, 'Failed to fork the repo!')
        return
    forked_project = response.json()
    retval = is_still_vulnerable(proj, forked_project['html_url'])
    if retval != 0:
        #db.pause_project(proj['id'], PAUSED_PROJECT_NOT_VULNERABLE_ANYMORE)
        failed_pullreq(proj['id'], PAUSED_PROJECT_NOT_VULNERABLE_ANYMORE, f'Project isn not vulnerable anymore.')
        return

    exit_code = is_patch_correct(proj)
    if exit_code != 5:
        #db.change_project_step(proj['id'], PAUSED_PATCHING_FAILED)
        failed_pullreq(proj['id'], PAUSED_PATCHING_FAILED, f'Patching failed. exit code: {exit_code}')
        #failed_pullreq(proj['id'], exit_code, f'Patching failed. exit code: {exit_code}')
        return
    else:
        logging.info(f'Project patched successfully.')

    patched_file_path = conv_url_to_gh_path(proj['file_github_url'])
    try:
        with open(f'./webapp-local{patched_file_path}', 'rb') as patched_file:
            patched_file_buf = patched_file.read()
            if not upload_file_to_project(forked_project['full_name'], patched_file_path, patched_file_buf):
                failed_pullreq(proj['id'], PAUSED_UNKNOWN_ERROR_GHAPI, 'Uploading file to forked repo fail')
                return
            else:
                logging.info('Patch applied to the forked project')
    except Exception as e:
        failed_pullreq(proj['id'], PAUSED_UNKNOWN_ERROR_EXCEPTION, f'Something bad happened during applying patch')
        logging.error(e)
        return

    #return # NO PR FOR NOW

    branch_name = get_default_branch(forked_project['full_name'])
    logging.info(f"Default branch name is {branch_name}")
    logging.info(f"Attempting to send a PULL Request")
    r = requests.post(f"https://api.github.com/repos/{proj['project_name']}/pulls", headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }, data=json.dumps({
        'base': branch_name,
        'head': f"{AUTHOR_GH_NAME}:{branch_name}",
        'body': generate_report(db.get_by_id(proj['id']), issue_id),
        'title': PULL_REQUEST_TITLE,
        'maintainer_can_modify': True,
    }))
    #print(r)
    if r.status_code != 201:
        failed_pullreq(proj['id'], PAUSED_UNKNOWN_ERROR_GHAPI, 'Failed to fork the repo!')
        return
    else:
        r = r.json()
        pull_req_url = r['html_url']
        logging.info(f'PULL request sent: {pull_req_url}')

    db.set_pull_request(proj['id'], r['url'])


if __name__ == "__main__":
    project_id = sys.argv[1]
    if input('About to send pull requests from your account. Do you want to proceed? (Y/N)').lower() != 'y':
        exit()
    if not project_id:
        print("No project ID given")
        sys.exit(4)
    if os.path.isfile(LOCK_FILENAME):
        print("Already running")
        exit(0)
    open(LOCK_FILENAME, "w").close()
    atexit.register(lambda: os.unlink(LOCK_FILENAME))
    time.sleep(3)
    #while True: # Uncomment to keep it running as pipeline
    to_pull_projects = db.get_patchready_projects(project_id)
    #print(to_pull_projects)
    time.sleep(5)
    for p in to_pull_projects:
        send_pull_req(p)
        print('-----------')
        time.sleep(5)
        # Temporary to make send single pull requests
        break
    #break
