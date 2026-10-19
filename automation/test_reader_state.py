"""Revision continuity must not silently move a check to a different practice."""
import json
import tempfile
import unittest
from pathlib import Path
from bible import digest
from reader_state import storage_identity


class ReaderStateTests(unittest.TestCase):
    def previous(self, root, *, storage='', checks=('첫 실천', '다음 실천'), body_issue='old-run', meta_issue='old-run', version='bnoc-reader-1.2'):
        attr = ' data-storage-issue="' + storage + '"' if storage else ''
        meta = json.dumps(dict(issueId=meta_issue, templateVersion=version))
        labels = ''.join('<label><input type="checkbox"><span>'+x+'</span></label>' for x in checks)
        raw = ('<html><body data-issue="'+body_issue+'"'+attr+'><section class="chapter checklist">'+labels+'</section><script type="application/json" id="bnoc-provenance">'+meta+'</script></body></html>').encode()
        (root/'original.html').write_bytes(raw)
        return dict(revision=dict(originalSha256=digest(raw)), practices=list(checks))

    def test_new_article_uses_its_own_identity_without_reading_an_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(storage_identity({}, tmp, 'new-run'), 'new-run')

    def test_existing_generic_article_keeps_exact_note_and_check_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); m=self.previous(root)
            self.assertEqual(storage_identity(m, root, 'second-run'), 'old-run')

    def test_later_revision_keeps_the_original_storage_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); m=self.previous(root, storage='first-run')
            self.assertEqual(storage_identity(m, root, 'third-run'), 'first-run')

    def test_reordered_or_reworded_practices_require_explicit_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); m=self.previous(root)
            for practices in (list(reversed(m['practices'])), ['첫 실천', '다른 실천']):
                with self.subTest(practices=practices), self.assertRaisesRegex(ValueError, 'Practice wording/order changed'):
                    storage_identity(dict(m, practices=practices), root, 'new-run')

    def test_whitespace_and_inline_markup_do_not_change_practice_meaning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); m=self.previous(root, checks=('첫 <strong>실천</strong>', '다음\n 실천'))
            m['practices']=['첫 실천', '다음 실천']
            self.assertEqual(storage_identity(m, root, 'new-run'), 'old-run')

    def test_changed_original_snapshot_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); m=self.previous(root)
            (root/'original.html').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'revision snapshot'):
                storage_identity(m, root, 'new-run')

    def test_mismatched_issue_metadata_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); m=self.previous(root, meta_issue='different-run')
            with self.assertRaisesRegex(ValueError, 'inconsistent'):
                storage_identity(m, root, 'new-run')

    def test_ambiguous_or_unrecognized_reader_identity_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); m=self.previous(root, version='future-unknown')
            with self.assertRaisesRegex(ValueError, 'Unknown previous reader'):
                storage_identity(m, root, 'new-run')
            m=self.previous(root)
            raw=(root/'original.html').read_bytes()+b'<body data-issue="another">'
            (root/'original.html').write_bytes(raw);m['revision']['originalSha256']=digest(raw)
            with self.assertRaisesRegex(ValueError, 'Ambiguous'):
                storage_identity(m, root, 'new-run')

    def test_legacy_document_does_not_guess_a_native_storage_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=b'<html><body><textarea data-note="action"></textarea></body></html>'
            (root/'original.html').write_bytes(raw)
            self.assertEqual(storage_identity(dict(revision=dict(originalSha256=digest(raw))), root, 'new-run'), 'new-run')


if __name__ == '__main__':
    unittest.main()
