#!/usr/bin/env python3
import requests
import urllib.parse

def get_npm_projects(repo):
	repo = urllib.parse.quote_plus(repo)
	related_packages = requests.get(f'https://deps.dev/_/project/github/{repo}').json()['relatedPackages']['packages']
	result = []
	for p in related_packages:
		if(p['system'] == 'NPM'):
			result.append(p['name'])
	return result
get_npm_projects('expressjs/express')

