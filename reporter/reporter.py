import logging
import os
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
from modules.email import extract_email
from modules.llmfix import patch_code
from utils.database import fetch_project_without_cvss, update_cvss, fetch_project_at_step, get_all
from utils.tools import gh_url_to_raw, gh_url_to_path
from modules.cvss import CVSS
from modules.email import extract_email, extract_email2
from utils.enums import *

dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
LOCK_FILENAME = "/tmp/0d-reporter.running"

def pick_lock():
    os.remove(LOCK_FILENAME)

def check_repos_with_advisory(skip):
    projs = get_all(STEP_PATCH_READY)

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

    #print(skip)

    for i, p in enumerate(projs):
    #for i, p in enumerate(projs[skip:]):
        if i<= skip: continue
        #print(p['id'], skip)
        #if p['id'] != skip: continue
        print(extract_email(f"https://github.com/{p['project_name']}", GITHUB_TOKEN))
        print(extract_email2(f"https://github.com/{p['project_name']}", GITHUB_TOKEN))
        report = f"""Path traversal Vulnerability in https://github.com/{p['project_name']}

{p['stars_count']}

Description:
Due to unsafe usage of `path.join`, https://github.com/{p['project_name']} is vulnerable to Local File Inclusion vulnerability.
You can read more about this vulnerability and its side effects here: https://cwe.mitre.org/data/definitions/22.html

The vulnerable code is at .{gh_url_to_path(p['file_github_url'])} file, which you can access online via: {p['file_github_url']}
If any of `path.join` arguments is a relative path to the parent directory (../), the returned path can be outside the intended directory and this might lead to leakage of sensitive files.

Running the project:
{format_run_method(p['file_github_url'],p['run_method'])}

Verified proof-of-concept(poc) to read passwd file(Path traversal vulnerability):
```bash
curl --path-as-is server_address:port/{p['poc'].replace('flag.txt', 'etc/passwd')}
```

{format_dos(p['is_vulnerable_to_dos'])}

By default, running the vulnerable file opens a port in the {'localhost only' if str(p['is_local'])=='1' else 'network' } scope. Thus the Attack Vector (AV) of CVSS is: {format_network(p['is_local'])}

Impact:
We've calculated the base score of the vulnerability as {p['base_score']:,.2}, with a severity of "{p['severity']}" using following the following vector_string: {p['vector_string']}
You can view the CVSS score online via: https://www.first.org/cvss/calculator/3.1#{p['vector_string']}


Mitigation:
We also prepared a patch, which we believe is secure against this attack. Patch file content:
```
{open(f'patches/{p["id"]}.patch').read()}
```

You can apply the patch by using the `patch` command:
```bash
patch --fuzz=3 --ignore-whitespace --verbose ".{os.path.dirname(gh_url_to_path(p['file_github_url']))}" -i patchfile.patch
```

This patch is generated with the help of AI, we verified it's working but still we recommend you verify that it correctly mitigates the bug and doesn't hurt the functionality of your software.
"""
        print(report)
        print('---------------')
        break

if __name__ == "__main__":
    if os.path.isfile(LOCK_FILENAME):
        print("Already running")
        exit(0)
    open(LOCK_FILENAME, "w").close()
    atexit.register(pick_lock)
    import sys
    skip=int(sys.argv[1])
    check_repos_with_advisory(skip)



