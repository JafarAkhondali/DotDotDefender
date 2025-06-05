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
import tempfile
import os
from utils.database import fetch_project_without_cvss, update_cvss, fetch_project_at_step, get_all
from utils.tools import gh_url_to_raw, gh_url_to_path
from modules.cvss import CVSS
from modules.email import extract_email
from modules.email import extract_email
from modules.llmfix import patch_code
from utils.enums import *


def create_github_issue(github_token, repository, title, body):
    """
    Create an issue on a specified GitHub repository.

    Args:
    github_token (str): GitHub personal access token.
    repository (str): Repository name in the format 'username/repo'.
    title (str): The title of the issue.
    body (str): The detailed description of the issue.

    Returns:
    dict: A dictionary containing the response from the GitHub API.
    """
    # Endpoint to create an issue at the specified repository
    url = f"https://api.github.com/repos/{repository}/issues"

    # Headers to authorize and accept the response
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Issue data
    data = {
        "title": title,
        "body": body
    }

    # Make the POST request to create an issue
    response = requests.post(url, headers=headers, data=json.dumps(data))

    # Check for successful request
    if response.status_code == 201:
        return response.json()  # Return the created issue details as JSON
    else:
        # Handle errors
        return {"error": response.status_code, "message": response.text}


dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

LOCK_FILENAME = "/tmp/0d-reporter-pr.running"


def pick_lock():
    os.remove(LOCK_FILENAME)


def check_repos_with_advisory(skip):
    print('querying')
    projs = get_all(STEP_PATCH_READY)
    print('query done')
    CHUNK = 700
    sent_issues = 0
    offset = 0
    for i, p in enumerate(projs):
        if p['stars_count'] >= 100:
            continue

        if offset <= skip:
            offset += 1
            continue

        if sent_issues >= CHUNK:
            break

        rep_address = p['project_name']
        issue = create_github_issue(GITHUB_TOKEN, rep_address, "Vulnerability report",
                                    f"""We conduct research on vulnerabilities in open-source software. We have discovered and verified a high-severity vulnerability in your project({p['project_name']}). Explaining the vulnerability further in this issue could allow malicious users to access details, so we recommend [enabling private vulnerability reporting on GitHub](https://docs.github.com/en/code-security/security-advisories/working-with-repository-security-advisories/configuring-private-vulnerability-reporting-for-a-repository) to discuss this matter confidentially.
        After you have enabled this feature, please add a comment to this issue so we can continue our discussion. If you have any questions, feel free to leave a reply here.""")
        print(issue)
        print(rep_address)
        if 'error' in issue and issue['error'] != 410:
            break
        time.sleep(10)
        sent_issues += 1
        print('---------------')


if __name__ == "__main__":
    if input('About to open Github Issues from your account. Do you want to proceed? (Y/N)').lower() != 'y':
        exit()
    if os.path.isfile(LOCK_FILENAME):
        print("Already running")
        exit(0)
    open(LOCK_FILENAME, "w").close()
    atexit.register(pick_lock)
    import sys

    skip = int(sys.argv[1])
    check_repos_with_advisory(skip)
