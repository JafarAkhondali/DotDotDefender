import dotenv
import random
import requests
import json
import os
import glob
import re
import time
import logging
import nltk
import utils.database as db
from sklearn.feature_extraction.text import TfidfVectorizer
from utils.enums import *
from nltk.tokenize import RegexpTokenizer
from utils.tools import gh_url_to_raw

# Ensure that NLTK tokens are downloaded
nltk.download("punkt")

if not os.path.exists("downloads"):
    os.mkdir("downloads")

dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
SEARCH_API_URL = "https://api.github.com/search/code"
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
REPOS = []
REPO_DETAILS = {}
TRIED_WORDS = []
COUNT_OF_RANDOM_WORDS = 1
PAGE_SIZE = 100
MAX_PAGES = 10
ALLOW_DUPLICATE_WORDS = False
MIN_GITHUB_STARS = int(os.getenv("MIN_GITHUB_STARS", 200))
BASE_QUERY = "http.createServer fs read file path req.url"


def tokenize_code(content):
    """
    Tokenize the source code content. This function can be enhanced to
    handle source code-specific tokens better.
    """
    tokenizer = RegexpTokenizer(r"\w+")
    return tokenizer.tokenize(content)


def compute_tfidf(directory_path, lang):
    """
    Compute the TF/IDF for files in the given directory and return a sorted list of tuples (term, score).
    """
    # Initialize a TfidfVectorizer with the custom tokenizer and binary=True to focus on presence/absence of words
    vectorizer = TfidfVectorizer(tokenizer=tokenize_code, lowercase=True, binary=True)

    # Initialize an empty list to store the contents of each file
    file_contents = []

    # Iterate over each file in the directory, reading the content and adding it to the list
    # for filename in os.listdir(directory_path):
    for filename in glob.glob(os.path.join(directory_path, f"*.{lang}")):
        filepath = os.path.join(directory_path, filename)
        if os.path.isfile(filepath):
            with open(filepath, "r", encoding="utf-8", errors="ignore") as file:
                file_contents.append(file.read())

    # Fit the TF/IDF model
    tfidf_matrix = vectorizer.fit_transform(file_contents)

    # Sum tfidf frequency of each term through documents
    sums = tfidf_matrix.sum(axis=0)

    # Connecting term to its sums frequency
    terms = vectorizer.get_feature_names_out()
    scores = [(term, sums[0, idx]) for term, idx in zip(terms, range(sums.shape[1]))]

    # Sort the items with the highest scores first
    sorted_scores = sorted(scores, key=lambda x: x[1], reverse=True)
    base_query_terms = BASE_QUERY.lower().split(" ")
    return list(
        filter(lambda item: item[0].lower() not in base_query_terms, sorted_scores)
    )


def make_safe_filename(s):
    return re.sub(r"[^a-zA-Z0-9_\.-]", "_", s)


def get_rate_limit_reset_time(headers):
    return int(headers.get("X-RateLimit-Reset", 0))


def get_repo_details(repo_api_url):
    """Get repository details including the star count."""
    response = requests.get(repo_api_url, headers=HEADERS)
    return response.json()


def get_rate_limit_remaining(headers):
    return int(headers.get("X-RateLimit-Remaining", 0))


def search_code(query, lang, page, items):
    """Search for code snippets in repositories with pagination."""
    print(f"Parsing page {page}")
    params = {"q": f"language:{lang} {query}", "per_page": PAGE_SIZE, "page": page}
    response = requests.get(SEARCH_API_URL, headers=HEADERS, params=params)
    try:
        items += response.json()["items"]
        rate_limit_remaining = get_rate_limit_remaining(response.headers)
        if rate_limit_remaining <= 1:
            reset_time = get_rate_limit_reset_time(response.headers)
            sleep_time = reset_time - time.time() + 2  # Adding 2 seconds buffer
            print(f"Chill... waiting rate-limit: {sleep_time}")
            if sleep_time > 0:
                time.sleep(max(sleep_time, 61))
        if "Link" in response.headers:
            links = response.headers["Link"].split(", ")
            next_link = [link for link in links if 'rel="next"' in link]
            if len(next_link) == 0:
                # Reached last page
                return
            print(f"Going deeper ...")
            search_code(query, lang, page + 1, items)
    except Exception as e:
        print("Corner case rate limit, retrying in 60s")
        time.sleep(60)
        return search_code(query, lang, page, items)


def find_repos(lang, last_query, keyword_index, keywords):
    items = []
    # Clean hack, items will be filled with results
    print(f"Current query: {last_query}")
    search_code(last_query, lang, 1, items)
    if len(items) == 0:
        logging.info("Nothing...")
        return []

    if len(items) == (PAGE_SIZE * MAX_PAGES):
        # This keyword still has more results that we didn't catch. Keep this keyword, and include
        # more unique words to access unseen samples, until we can reach 95% of the remaining samples
        # Here, we add current keyword to ours, and add index, so it'll go inside it nested.
        while True:
            # Prevent duplicate queries
            if keywords[keyword_index][0] in last_query:
                keyword_index += 1
                continue
            break
        find_repos(
            lang,
            f"{last_query} {keywords[keyword_index][0]}",
            keyword_index + 1,
            keywords,
        )

    return items


def get_next_query():
    words = {}
    for _ in range(5):
        repo = REPO_DETAILS[random.choice(REPOS)]
        download_url = gh_url_to_raw(repo["html_url"])
        content = requests.get(download_url, headers=HEADERS).text
        regex = r"\b\w+\b"
        l = re.findall(r"\b\w+\b", content)
        for w in l:
            if w not in words:
                words[w] = 0
            words[w] += 1
    words = sorted(words.items(), key=lambda x: x[1])
    if len(words) < 1:
        print("?? this probably shouldnt happen")
        return ""

    new_query = []
    for w in words[::-1]:
        if len(new_query) >= COUNT_OF_RANDOM_WORDS:
            break
        w = w[0]
        if ALLOW_DUPLICATE_WORDS or w not in TRIED_WORDS:
            new_query.append(w)
            TRIED_WORDS.append(w)
    return f"{BASE_QUERY} {' '.join(new_query)}"


def save_state():
    with open("./state.json", "w") as f:
        f.write(
            json.dumps(
                {
                    "REPOS": REPOS,
                    "REPO_DETAILS": REPO_DETAILS,
                    "TRIED_WORDS": TRIED_WORDS,
                }
            )
        )


def read_state():
    if not os.path.isfile("./state.json"):
        return
    global REPOS, REPO_DETAILS, TRIED_WORDS
    with open("./state.json", "r") as f:
        r = json.loads(f.read())
        REPOS = r["REPOS"]
        REPO_DETAILS = r["REPO_DETAILS"]
        TRIED_WORDS = r["TRIED_WORDS"]


def download_file(url, path, proj_id):
    """Download a file from GitHub."""
    db.change_project_step(proj_id, STEP_CLONING)
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        try:
            with open(f"./downloads/{path}", "wb") as f:
                f.write(response.content)
            db.update_filename(proj_id, path)
            db.change_project_step(proj_id, STEP_CLONED)
            logging.info(f"Successfully downloaded file {path}")
        except Exception as error:
            db.pause_project(proj_id, PAUSED_CLONE_FS_SAVE_FAILED)
            logging.error(f"Failed to clone {path} - Error: {error}")
            return
    else:
        db.pause_project(proj_id, PAUSED_HTTP_CLONE_FAILED)
        logging.info(f"Failed to clone {path}")


def pass_to_db(repo):
    repo_details = REPO_DETAILS[repo]
    repo_api_url = repo_details["repository"]["url"]
    stars = get_repo_details(repo_api_url).get("stargazers_count", 0)

    if stars >= MIN_GITHUB_STARS:
        file_path = os.path.basename(repo_details["path"])
        repo_url = repo_details["repository"]["html_url"]
        name_with_owner = repo_details["repository"]["full_name"]
        filename = make_safe_filename(f"{name_with_owner}-{file_path.split('/')[-1]}")

        download_url = gh_url_to_raw(repo_details["html_url"])

        pending_project_id = db.add_project(
            repo_details["repository"]["full_name"], download_url, stars
        )
        download_file(download_url, filename, pending_project_id)

def main_wip():
    read_state()
    LANGS = [
        ("javascript", "js")
    ]

    next_query = BASE_QUERY

    for lang, extension in LANGS:
        keywords = compute_tfidf("../downloads", extension)
        keywords = keywords[::-1]
        keywords = list(filter(lambda x: x[1] >= 0.401, keywords))
        print(keywords)
        print(len(keywords))
        for i, keyword in enumerate(keywords):
            print(keyword, i)
            try:
                print(f"Next query: `{next_query}`")
                items = find_repos(lang, f"{BASE_QUERY} {keywords[i][0]}", i, keywords)
                found = {}
                for item in items:
                    found[item["repository"]["full_name"]] = item
                for r in found:
                    if r not in REPOS:
                        REPOS.append(r)
                        REPO_DETAILS[r] = found[r]
                        pass_to_db(r)
                print(f"Count of found repositories: {len(REPOS)}")
                save_state()
            except Exception as e:
                print(e)


if __name__ == "__main__":
    main_wip()
