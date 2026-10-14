import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import publish_release
import repository_access
import archive_input


def entry_script():
    workflow=(Path(__file__).parents[1]/'.github/workflows/pack.yml').read_text()
    return textwrap.dedent(workflow.split("python3 - <<'PYCODE'",1)[1].split('\n          PYCODE',1)[0])


class WorkflowEntryTests(unittest.TestCase):
    def test_input_resolution_keeps_download_urls_out_of_job_outputs(self):
        url='https://storage.invalid/input.zip?token=private'
        for digest in ('', 'a'*64):
            with tempfile.TemporaryDirectory() as temp:
                output=Path(temp)/'output'
                with patch.dict(os.environ,GITHUB_OUTPUT=str(output)), patch.object(archive_input,'settings',return_value=(url,digest)):
                    archive_input.resolve()
                values=dict(line.split('=',1) for line in output.read_text().splitlines())
                self.assertEqual(values['input_revision'],archive_input.input_identity(url,digest))
                self.assertNotIn(url,output.read_text())

    def test_private_caller_uses_callee_commit_and_does_not_export_a_secret(self):
        digest='1'*64
        sha='a'*40
        run={'head_sha':'b'*40,'referenced_workflows':[{
            'path':'jiayx/d2r-mobile-build/.github/workflows/pack.yml@feat/build-template','sha':sha}]}
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'output'
            env={'GITHUB_REPOSITORY':'owner/repo','GITHUB_RUN_ID':'123',
                 'GAME_ARCHIVE':json.dumps({'url':'https://storage.invalid/input.zip','sha256':digest}),'GITHUB_OUTPUT':str(output)}
            with patch.dict(os.environ,env), patch.object(repository_access.subprocess,'check_output',side_effect=[json.dumps({'private':True}),json.dumps(run)]):
                exec(compile(entry_script(), 'workflow-entry', 'exec'), {})
            values=dict(line.split('=',1) for line in output.read_text().splitlines())
            self.assertEqual(values['tools_commit'],sha)
            self.assertNotIn('input_revision',values)
            self.assertNotIn(digest,output.read_text())

    def test_public_destination_fails_before_resolving_or_reading_inputs(self):
        with patch.dict(os.environ, GITHUB_REPOSITORY='owner/repo'), patch.object(repository_access.subprocess,'check_output',return_value=json.dumps({'private':False})) as api:
            with self.assertRaisesRegex(SystemExit,'PRIVATE repository'):
                exec(compile(entry_script(), 'workflow-entry', 'exec'), {})
            self.assertEqual(api.call_count,1)

    def test_publish_helpers_cannot_upload_to_a_public_repository(self):
        metadata={'private':False,'full_name':'owner/repo'}
        with patch.object(repository_access.subprocess,'check_output',return_value=json.dumps(metadata)), patch.object(publish_release,'gh') as mutate:
            for call in (lambda:publish_release.ensure_release('owner/repo','tag','title',Path('notes')),
                         lambda:publish_release.upload_verified('owner/repo','tag',[]),
                         lambda:publish_release.publish_complete('owner/repo','tag','notes')):
                with self.assertRaisesRegex(ValueError,'private repository'):
                    call()
            mutate.assert_not_called()


if __name__=='__main__':
    unittest.main()
