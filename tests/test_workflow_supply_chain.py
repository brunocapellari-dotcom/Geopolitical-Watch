from __future__ import annotations

import re
import unittest
from pathlib import Path


WORKFLOWS = Path('.github/workflows')
USES_RE = re.compile(r'^\s*-?\s*uses:\s*([^\s#]+)', re.MULTILINE)
SHA_RE = re.compile(r'^[0-9a-f]{40}$')


class WorkflowSupplyChainTests(unittest.TestCase):
    def test_external_actions_are_pinned_to_full_commit_sha(self) -> None:
        violations: list[str] = []
        for path in sorted(WORKFLOWS.glob('*.yml')) + sorted(WORKFLOWS.glob('*.yaml')):
            text = path.read_text(encoding='utf-8')
            for ref in USES_RE.findall(text):
                if ref.startswith('./'):
                    continue
                if '@' not in ref:
                    violations.append(f'{path}: missing @ref in {ref}')
                    continue
                action, revision = ref.rsplit('@', 1)
                if not SHA_RE.fullmatch(revision):
                    violations.append(f'{path}: {action}@{revision} is not pinned to a 40-char SHA')
        self.assertEqual(violations, [], '\n'.join(violations))

    def test_workflows_use_minimal_read_permissions_by_default(self) -> None:
        violations: list[str] = []
        for path in sorted(WORKFLOWS.glob('*.yml')) + sorted(WORKFLOWS.glob('*.yaml')):
            text = path.read_text(encoding='utf-8')
            if path.name == 'gcp-release.yml':
                # Deployment needs OIDC, but no repository write permission.
                if 'id-token: write' not in text or 'contents: read' not in text:
                    violations.append(f'{path}: production release must use id-token: write + contents: read')
                continue
            if 'permissions:' not in text or 'contents: read' not in text:
                violations.append(f'{path}: missing explicit contents: read permissions')
        self.assertEqual(violations, [], '\n'.join(violations))


if __name__ == '__main__':
    unittest.main()
