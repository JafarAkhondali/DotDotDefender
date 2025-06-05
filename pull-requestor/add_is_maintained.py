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
import requests
import re
import base64
import utils.database as db
from tqdm import tqdm
from typing import Optional, List, Dict
from utils.enums import *

GITHUB_API_URL = "https://api.github.com"

# Replace these with your own GitHub username and personal access token
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
LOCK_FILENAME = "/tmp/0d-add-is-maintained.running"

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

import requests
from datetime import datetime, timedelta


def check_repo_status(github_token, repo_name):
    # GitHub API URLs
    repo_url = f"https://api.github.com/repos/{repo_name}"
    commits_url = f"https://api.github.com/repos/{repo_name}/commits"
    readme_url = f"https://api.github.com/repos/{repo_name}/readme"

    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json',
    }

    # Get repository details
    repo_response = requests.get(repo_url, headers=headers)
    if repo_response.status_code != 200:
        return False

    repo_data = repo_response.json()

    # Check if the repository is marked as unmaintained
    if repo_data.get('archived', False):
        return False

    # Check the latest commit date
    commits_response = requests.get(commits_url, headers=headers)
    if commits_response.status_code != 200:
        return False

    commits_data = commits_response.json()
    latest_commit_date_str = commits_data[0]['commit']['committer']['date']
    latest_commit_date = datetime.strptime(latest_commit_date_str, "%Y-%m-%dT%H:%M:%SZ")

    one_year_ago = datetime.now() - timedelta(days=365)
    if latest_commit_date < one_year_ago:
        return False

    # Check the README file for 'unmaintained' or 'not maintained'
    readme_response = requests.get(readme_url, headers=headers)
    if readme_response.status_code == 200:
        readme_data = readme_response.json()
        readme_content = requests.get(readme_data['download_url']).text.lower()
        if 'unmaintained' in readme_content or 'not maintained' in readme_content or 'deprecat' in readme_content:
            return False
        elif 'maintain' in readme_content:
            print(readme_content)

    return True

if __name__ == "__main__":
    if os.path.isfile(LOCK_FILENAME):
        print("Already running")
        exit(0)
    open(LOCK_FILENAME, "w").close()
    atexit.register(lambda: os.unlink(LOCK_FILENAME))
    while True:
        projects = db.get_maintained_status_missing_projects()
        for p in tqdm(projects):
            try:
                is_maintained = check_repo_status(GITHUB_TOKEN, p['project_name'])
                print(f"{p['project_name']} is {'maintained' if is_maintained else 'unmaintained'}")
                is_maintained = 1 if is_maintained else 0
                db.set_field(p['id'], 'is_maintained', is_maintained)
            except Exception as e:
                print('Failed...')
                time.sleep(10)
            print('-----------')
            time.sleep(1)