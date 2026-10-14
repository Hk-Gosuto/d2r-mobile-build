"""Require a private destination before accessing game inputs or publishing."""
import json
import os
import subprocess


def require_private(repo=None):
    repo = repo or os.environ['GITHUB_REPOSITORY']
    metadata = json.loads(subprocess.check_output(
        ['gh', 'api', 'repos/' + repo], text=True))
    if metadata.get('private') is not True or metadata.get('full_name') != repo:
        raise ValueError('Game builds require your own private repository. Use the template to create one.')
    return repo
