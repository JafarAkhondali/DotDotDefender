import re
import subprocess


def gh_url_to_raw(url):
    return re.sub('blob/[a-fA-F0-9]+', 'HEAD', url) \
        .replace("github.com", "raw.githubusercontent.com")


def gh_url_to_path(url):
    head = '/HEAD/'
    return url[url.index(head) + len(head) - 1:]

def read_file(file_name):
    with open(file_name) as f:
        return f.read()

def runcommand(cmd):
    proc = subprocess.Popen(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            shell=True,
                            universal_newlines=True)
    std_out, std_err = proc.communicate()
    return proc.returncode, std_out, std_err
