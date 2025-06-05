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
from typing import Optional, List, Dict
from utils.tools import gh_url_to_path
from utils.enums import *

GITHUB_API_URL = "https://api.github.com"

# Replace these with your own GitHub username and personal access token
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
LOCK_FILENAME = "/tmp/0d-add-first-appeared.running"

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

def get_commit_history(owner: str, repo: str, file_path: str, headers: dict) -> List[Dict]:
    """Fetch the commit history for a specific file."""
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/commits"
    params = {
        "path": file_path,
        "per_page": 100  # Adjust as needed for pagination
    }
    all_commits = []
    while url:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        commits = response.json()
        all_commits.extend(commits)
        # Check if there's another page
        if 'next' in response.links:
            url = response.links['next']['url']
        else:
            url = None
    return all_commits


def get_file_content_at_commit(owner: str, repo: str, commit_sha: str, file_path: str, headers: dict) -> Optional[str]:
    """Fetch the file content at a specific commit."""
    # Use the specific commit endpoint to get file changes
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/git/trees/{commit_sha}?recursive=1"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    tree_data = response.json()

    # Find the file in the tree data
    for item in tree_data['tree']:
        if item['path'] == file_path and item['type'] == 'blob':
            # Fetch the blob content
            blob_url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/git/blobs/{item['sha']}"
            blob_response = requests.get(blob_url, headers=headers)
            blob_response.raise_for_status()
            blob_data = blob_response.json()
            wtf = requests.utils.unquote(blob_data['content']).encode().decode('utf-8')
            wtf = base64.b64decode(wtf).decode('utf8')
            return wtf

    return None


def find_first_commit_date_with_keyword(file_url: str, keyword: str, token: str) -> Optional[str]:
    """Find the date when a keyword first appeared in a file."""
    # Extract the repository info from the URL
    pattern = r"https://raw\.githubusercontent\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/(?P<branch>[^/]+)/(?P<file_path>.+)"
    match = re.match(pattern, file_url)
    if not match:
        raise ValueError("The URL format is incorrect.")

    owner = match.group("owner")
    repo = match.group("repo")
    branch = match.group("branch")
    file_path = match.group("file_path")

    # Setup the headers with the GitHub token
    headers = {
        "Authorization": f"token {token}"
    }

    # Get the commit history for the file
    commits = get_commit_history(owner, repo, file_path, headers)

    # Sort commits by date in ascending order
    commits.sort(key=lambda x: x['commit']['committer']['date'])

    # Iterate over each commit and check for the keyword
    for commit in commits:
        commit_sha = commit['sha']
        commit_date = commit['commit']['committer']['date']
        try:
            # Get the file content at this commit
            file_content = get_file_content_at_commit(owner, repo, commit_sha, file_path, headers)
            print(commit_sha)
            if file_content and keyword in file_content:
                return commit_date.split('T')[0]  # Return only the date part
        except Exception as e:
            logging.error(f"Error retrieving content for commit {commit_sha}: {e}")

    return None


def find_first_commited_date(proj):
    for keyword in ['path.join', 'createServer']:
        commit_date = find_first_commit_date_with_keyword(proj['file_github_url'], keyword, GITHUB_TOKEN)
        if commit_date:
            return commit_date
    return None


if __name__ == "__main__":
    if os.path.isfile(LOCK_FILENAME):
        print("Already running")
        exit(0)
    open(LOCK_FILENAME, "w").close()
    atexit.register(lambda: os.unlink(LOCK_FILENAME))
    while True:
        projects = db.get_firstappeard_projects()
        for p in projects:
            try:
                commit_date = find_first_commited_date(p)
                print(p['project_name'])
                if not commit_date:
                    print('Commit date not found.')
                print(commit_date)
                db.set_field(p['id'], 'first_appeared_at', commit_date)
                print('-----------')
            except Exception as e:
                print('Failed...')
            time.sleep(5)
