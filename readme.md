# DotDot Defender

### Installation:

```bash
# Update env variables
cp env.example .env

# Run database image
sudo docker-compose up -d

#Docker is also required for pipeline steps

pip3 install -r requirements.txt

# Install CodeQL - https://github.com/github/codeql-action/releases
```

### Usage:

This programs consists of several components, each of them are designed to ran independently, contributing to the pipeline.
1. Scrapper: Searches for specific patterns of vulnerable code(`scrapper/recursive-scrapper.py`)
2. Static analysis: Validates the vulnerability by running SemGrep `sast/grep.py` with specific payload
3. PoC checker: Runs the program and executes the payload ( `poc-checker` must be run as root for docker commands)
Note: In this directory, there are 3 different poc checkers and all of them must ran to complete this step: `run-poc-network.py`, `run-poc-local.py` and `run-poc-dos.py`   
4. Reporter: Calculates CVSS Score with `calculate_cvss_scores.py` and prepares a fix using GPT4 in `patcher.py`
5. Reporter: Run `pather.py` to verify vulnerability still exists, and apply a verified patch using LLM.
6. pull-requester: Run `add_first_appeared.py` to get the time when the first vulnerable commit was seen.
7. pull-requester: Run `run.py` to re-verify the patch and send pull request.