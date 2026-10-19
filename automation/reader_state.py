"""Keep a known reader's local records attached to the same article on revision."""
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from bible import digest


class _PreviousReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.bodies = []
        self.provenance = []
        self.checks = []
        self.stack = []
        self.label = None
        self.metadata = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'body':
            self.bodies.append(a)
        if tag == 'script' and a.get('id') == 'bnoc-provenance':
            self.metadata = []
        if tag == 'label' and any('checklist' in x.get('class', '').split() for _, x in self.stack):
            if self.label is not None:
                raise ValueError('Nested practice labels need an explicit state mapping')
            self.label = []
        if tag not in {'input', 'img', 'br', 'hr', 'meta', 'link', 'source', 'wbr'}:
            self.stack.append((tag, a))

    def handle_endtag(self, tag):
        if tag == 'label' and self.label is not None:
            self.checks.append(_words(''.join(self.label)))
            self.label = None
        if tag == 'script' and self.metadata is not None:
            self.provenance.append(json.loads(''.join(self.metadata)))
            self.metadata = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if self.label is not None:
            self.label.append(data)
        if self.metadata is not None:
            self.metadata.append(data)


def _words(text):
    return ' '.join(text.split())


def storage_identity(manuscript, run_dir, issue_id):
    """Reuse only a hash-bound generic reader with unchanged practice meanings.

    No localStorage values are read, copied, merged or deleted. In particular, an
    intentionally empty note or unchecked practice remains the existing value.
    Unknown legacy/native formats keep their own separately reviewed path.
    """
    revision = manuscript.get('revision')
    if not revision:
        return issue_id
    raw = (Path(run_dir) / 'original.html').read_bytes()
    if digest(raw) != revision.get('originalSha256'):
        raise ValueError('Reader state source differs from the revision snapshot')
    previous = _PreviousReader()
    previous.feed(raw.decode('utf-8-sig'))
    if not previous.provenance:
        return issue_id
    if len(previous.provenance) != 1 or len(previous.bodies) != 1:
        raise ValueError('Ambiguous previous reader identity')
    meta = previous.provenance[0]
    if meta.get('templateVersion') not in {'bnoc-reader-1.1', 'bnoc-reader-1.2'}:
        raise ValueError('Unknown previous reader state format')
    body = previous.bodies[0]
    if not body.get('data-issue') or meta.get('issueId') != body['data-issue']:
        raise ValueError('Previous reader issue identity is inconsistent')
    identity = body.get('data-storage-issue', body['data-issue'])
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,159}', identity):
        raise ValueError('Invalid previous reader storage identity')
    if previous.checks != [_words(x) for x in manuscript['practices']]:
        raise ValueError('Practice wording/order changed; an explicit state mapping is required')
    return identity
