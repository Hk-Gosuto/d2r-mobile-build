import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import ci
from source.configure import configure
from source.resolve import resolve_ref


class SourceSelectionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.upstream = self.root / 'upstream'
        self.upstream.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Build test')
        self.git('config', 'user.email', 'build@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        self.git('config', 'tag.gpgsign', 'false')
        (self.root / 'config').mkdir()
        (self.root / 'config/build-pins.json').write_text(json.dumps(ci.CONFIG))
        (self.upstream / 'source.txt').write_text('first\n')
        self.commit('first')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.upstream), *args],
                                       text=True, stderr=subprocess.DEVNULL).strip()

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '-m', message)
        return self.git('rev-parse', 'HEAD')

    def test_new_release_uses_its_own_tag_in_both_ipa_names(self):
        self.git('tag', 'v1.0.20')
        config = configure(self.root)
        self.assertEqual(config['upstream_commit'], self.git('rev-parse', 'v1.0.20'))
        self.assertEqual(ci.ipa_names(config), ('D2RMobile-v1.0.20.ipa', 'D2RMobile-v1.0.20-ios18.ipa'))
        self.git('tag', '-d', 'v1.0.20')
        self.git('tag', 'v1.0.21')
        self.assertEqual(configure(self.root)['build_label'], 'v1.0.21')

    def test_default_looks_up_the_latest_release_on_every_run(self):
        replies = [json.dumps({'tag_name': tag, 'draft': False, 'prerelease': False})
                   for tag in ('v1.0.20', 'v1.0.21')]
        with patch('source.resolve.subprocess.check_output', side_effect=replies) as api:
            self.assertEqual(resolve_ref('owner/upstream'), 'refs/tags/v1.0.20')
            self.assertEqual(resolve_ref('owner/upstream', '  '), 'refs/tags/v1.0.21')
            self.assertEqual(api.call_count, 2)
            api.assert_called_with(['gh', 'api', 'repos/owner/upstream/releases/latest'], text=True)

    def test_explicit_main_tag_or_commit_skips_release_lookup(self):
        with patch('source.resolve.subprocess.check_output') as api:
            for ref in ('main', 'my-feature', 'v1.0.20', 'a' * 40):
                self.assertEqual(resolve_ref('owner/fork', ref), ref)
            api.assert_not_called()

    def test_draft_prerelease_and_missing_release_cannot_be_selected(self):
        for release in ({'tag_name': 'v1.0.20', 'draft': True, 'prerelease': False},
                        {'tag_name': 'v1.0.21-beta', 'draft': False, 'prerelease': True},
                        {'message': 'Not Found'}):
            with self.subTest(release=release), patch('source.resolve.subprocess.check_output', return_value=json.dumps(release)):
                with self.assertRaisesRegex(ValueError, 'official release'):
                    resolve_ref('owner/upstream')

    def test_main_advances_and_each_build_records_the_current_checkout(self):
        self.git('tag', 'v1.0.20')
        release_commit = self.git('rev-parse', 'HEAD')
        (self.upstream / 'source.txt').write_text('new main feature\n')
        first_commit = self.commit('new feature')
        first = configure(self.root)
        self.assertEqual(first['build_label'], 'v1.0.20-src-' + first_commit[:12])
        (self.upstream / 'source.txt').write_text('another main feature\n')
        second_commit = self.commit('another feature')
        second = configure(self.root)
        self.assertEqual(second['upstream_commit'], second_commit)
        self.assertNotEqual(ci.ipa_names(first), ci.ipa_names(second))
        # A user's explicit tag or commit still selects that exact source.
        self.git('checkout', '--detach', release_commit)
        self.assertEqual(configure(self.root)['build_label'], 'v1.0.20')

    def test_fork_without_tags_uses_commit_and_discards_old_version_metadata(self):
        path = self.root / 'config/build-pins.json'
        config = json.loads(path.read_text())
        config.update(upstream_version='v1.0.13', upstream_commit='old-source',
                      build_label='v1.0.13', source_patch_sha256='old-patch')
        path.write_text(json.dumps(config))
        actual = configure(self.root)
        self.assertEqual(actual['build_label'], 'src-' + self.git('rev-parse', 'HEAD')[:12])
        self.assertNotIn('upstream_version', actual)
        self.assertNotIn('source_patch_sha256', actual)

    def test_local_patch_changes_the_output_identity(self):
        self.git('tag', 'v1.0.20')
        (self.upstream / 'source.txt').write_text('patched source\n')
        patch_data = self.git('diff') + '\n'
        self.git('checkout', '--', 'source.txt')
        patches = self.root / 'source-patches'
        patches.mkdir()
        patch = patches / 'feature.patch'
        patch.write_text(patch_data)
        config = configure(self.root)
        digest = hashlib.sha256(b'feature.patch\0' + patch.read_bytes()).hexdigest()
        self.assertEqual(config['build_label'], 'v1.0.20-patch-' + digest[:12])
        self.assertEqual(config['source_patch_sha256'], digest)
        self.assertEqual((self.upstream / 'source.txt').read_text(), 'patched source\n')

    def test_unresolved_or_unsafe_output_names_fail_before_publication(self):
        for config in ({}, {'build_label': '../release'}, {'build_label': ''}):
            with self.subTest(config=config), self.assertRaisesRegex(ValueError, 'Resolve'):
                ci.ipa_names(config)


if __name__ == '__main__':
    unittest.main()
