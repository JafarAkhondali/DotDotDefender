import re
import requests
from bs4 import BeautifulSoup

def extract_email2(repo_url, token):
    # Extract username and repo name from URL
    path_parts = repo_url.split('/')
    username = path_parts[-2]
    repo_name = path_parts[-1]

    # GitHub API endpoints
    user_api_url = f"https://api.github.com/users/{username}"
    repo_api_url = f"https://api.github.com/repos/{username}/{repo_name}/commits"
    # Headers to use GitHub API, optional: include 'Authorization': 'token YOUR_GITHUB_TOKEN'
    headers = {'Accept': 'application/vnd.github.v3+json', 'Authorization': f'token {token}'}

    # Get user data
    user_response = requests.get(user_api_url, headers=headers)
    if user_response.status_code == 200:
        user_data = user_response.json()
        # Check if public email is available
        if user_data.get('email') and 'noreply' not in user_data['email']:
            return user_data['email']

    # If no public email, fetch the latest commits
    commits_response = requests.get(repo_api_url, headers=headers)
    if commits_response.status_code == 200:
        commits_data = commits_response.json()
        if commits_data:
            # Get the latest commit URL and append '.patch'
            latest_commit_url = commits_data[0]['url']
            #print(latest_commit_url)
            patch_response = requests.get(latest_commit_url, headers=headers)
            if patch_response.status_code == 200:
                # Extract email from the patch
                res = patch_response.json()
                commiter_email=res['commit']['committer']['email']
                if 'noreply' not in commiter_email: return commiter_email
                return res['commit']['author']['email']
                #res = patch_response.json()
    return False



def extract_emails_and_links(text):
    """
  Extracts emails and links from a text string and returns separate lists.

  Args:
      text: The text string to extract emails and links from.

  Returns:
      A tuple containing two lists:
          - The first list contains all the extracted emails.
          - The second list contains all the extracted links.
  """
    emails = []
    links = []

    # Email regex pattern
    email_regex = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"

    # Link regex pattern (match common protocols)
    link_regex = r"(?:https?):\/\/[\w/\-?=%.]+\.[\w/\-&?=%.]+"

    # Find all emails
    emails.extend(re.findall(email_regex, text))

    # Find all links
    links.extend(re.findall(link_regex, text))

    return emails, links


def fetch_security_page(owner, repo, token):
    """
    Fetch the content of the .markdown-body element from the given URL.

    :param owner: The owner of the repository
    :param repo: The repository name
    :param token: Github token
    :return: The content of the .markdown-body element or None if not found
    """
    headers = {"Authorization": f"token {token}"} if token else {}
    response = requests.get(f"https://github.com/{owner}/{repo}/security", headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        markdown_body = soup.find(class_="markdown-body")
        if markdown_body:
            return str(markdown_body)
    return None


def advisory_report_button(owner, repo, token):
    """
    Fetch the content of the .markdown-body element from the given URL.

    :param owner: The owner of the repository
    :param repo: The repository name
    :param token: Github token
    :return: Checks if drafting security advisory is allowed
    """
    headers = {"Authorization": f"token {token}"} if token else {}
    response = requests.get(f"https://github.com/{owner}/{repo}/security", headers=headers)
    if response.status_code == 200:
        return "Report a vulnerability" in response.text
    return None


def fetch_readme_content(owner, repo, token):
    """
    Fetch the content of the README file from the given repository.

    :param owner: The owner of the repository
    :param repo: The repository name
    :param token: Github token
    :return: The content of the README file or None if not found
    """
    headers = {"Authorization": f"token {token}"} if token else {}
    api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        readme_data = response.json()
        readme_url = readme_data.get('download_url')
        if readme_url:
            readme_response = requests.get(readme_url)
            if readme_response.status_code == 200:
                return readme_response.text
    return None


def extract_emails_from_text(text):
    """
    Extract email addresses from text using regular expressions.
    """
    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    return email_pattern.findall(text)


def fetch_emails_from_github(owner, repo, token=None):
    """
    Fetch email addresses of maintainers from a GitHub repository.

    :param owner: The owner of the repository
    :param repo: The repository name
    :param token: GitHub API token for authentication (optional)
    """
    headers = {"Authorization": f"token {token}"} if token else {}
    base_url = f"https://api.github.com/repos/{owner}/{repo}"
    files_to_check = ['MAINTAINERS', 'AUTHORS', 'CONTRIBUTORS', 'README.md']
    emails = []

    # Check the specific files for email addresses
    for file_name in files_to_check:
        file_url = f"{base_url}/contents/{file_name}"
        response = requests.get(file_url, headers=headers)
        if response.status_code == 200:
            file_content = requests.get(response.json()['download_url']).text
            found_emails = extract_emails_from_text(file_content)
            if found_emails:
                emails.extend(found_emails)
                break  # Stop if we've found emails in one of the files

    # Fallback: If no emails found, get the most frequent committer's email
    if not emails:
        commits_url = f"{base_url}/commits"
        response = requests.get(commits_url, headers=headers)
        if response.status_code == 200:
            commits = response.json()
            email_counts = {}
            for commit in commits:
                commit_email = commit['commit']['author']['email']
                if commit_email not in email_counts:
                    email_counts[commit_email] = 0
                email_counts[commit_email] += 1
            # Find the email with the highest commit count
            most_common_email = max(email_counts, key=email_counts.get)
            emails.append(most_common_email)

    return emails


def extract_repo_owner_and_name(repo_url):
    return repo_url.split('/')[3:5]


def extract_email(repo_url, token):
    repo_owner, repo_name = extract_repo_owner_and_name(repo_url)
    # TODO Handle having security policy enabled.

    for name, method in extraction_methods.items():
        result = method(repo_owner, repo_name, token)
        if not result:
            continue

        if name == 'REPORT_ADVISORY':
            return {
                'method': name,
                'emails': None,
                'links': None
            }

        if name == 'MAINTAINERS':
            return {
                'method': name,
                'emails': result,
            }

        emails, links = extract_emails_and_links(result)
        emails = set(emails)
        links = set(links)
        return {
            'method': name,
            'emails': emails,
            'links': links
        }


extraction_methods = {
    'REPORT_ADVISORY': advisory_report_button,
    'SECURITY_PAGE': fetch_security_page,
    'README': fetch_readme_content,
    'MAINTAINERS': fetch_emails_from_github,
}

