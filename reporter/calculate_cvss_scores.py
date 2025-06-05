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
from utils.database import fetch_project_without_cvss, update_cvss, fetch_project_at_step
from utils.enums import *
from utils.tools import gh_url_to_raw, gh_url_to_path
from modules.cvss import CVSS
from modules.email import extract_email
from modules.llmfix import patch_code

dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
LOCK_FILENAME = "/tmp/0d-cvss.running"

def pick_lock():
    os.remove(LOCK_FILENAME)


def update_vuln_cvss():
    while True:
        row = fetch_project_without_cvss()
        if not row:
            return
        project_id, is_local, is_vulnerable_to_dos = row

        # Calculate CVSS score
        # Based on https://www.first.org/cvss/calculator/3.0#CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N
        cvss = CVSS()

        # Attack Vector (AV)
        attack_vector = {
            '1': 'L',  # if it's only vulnerable in localhost, it'll be (A)djacent
            '0': 'N'  # if it's vulnerable outside local, it should be (N)etwork
        }.get(str(is_local))
        cvss.set_metric('AV', attack_vector)

        # Attack Complexity (AC)
        # The attack payloads and execution methods are super easy, so (L)ow is hard-coded
        cvss.set_metric('AC', 'L')

        # Privileges Required (PR)
        # Payloads are all used anonymously, so (N)one is hard-coded
        cvss.set_metric('PR', 'N')

        # User Interaction (UI)
        # No user interaction, so (N)one is hard-coded
        cvss.set_metric('UI', 'N')

        # Scope (S)
        # Although in some examples scope my change(thus increase impact), we hard-code it to (U)nchanged to make to not
        # have biased results
        cvss.set_metric('S', 'U')

        # Confidentiality (C)
        # This vulnerability allows reading all files in operating system, so (H)igh is hard-coded for it
        cvss.set_metric('C', 'H')

        # Availability(A)
        # Available is calculated based on vulnerability status of dynamic checking on DOS
        # DOS_NOT_VULNERABLE
        availability = {
            '1': 'H',  # '1' means vulnerable to DOS -> (H)igh
            '2': 'N'  # '2' means not vulnerable to DOS -> (N)one
        }.get(str(is_vulnerable_to_dos))
        cvss.set_metric('A', availability)

        # Integrity (I)
        # To the best of our knowledge, this vulnerability doesn't affect integrity directly
        cvss.set_metric('I', 'N')

        vector_string = cvss.get_vector_string()
        base_score = cvss.calculate_base_score()
        severity = cvss.get_severity()

        update_cvss(project_id, vector_string, base_score, severity)


if __name__ == "__main__":
    if os.path.isfile(LOCK_FILENAME):
        print("Already running")
        exit(0)
    open(LOCK_FILENAME, "w").close()
    atexit.register(pick_lock)

    while True:
        logging.info("Updating CVSS scores")
        update_vuln_cvss()
        logging.info("CVSS scores are updated")
        time.sleep(5)
