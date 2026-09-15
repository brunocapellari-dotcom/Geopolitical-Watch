from __future__ import annotations

import re
import unittest
from pathlib import Path


WORKFLOWS = Path('.github/workflows')
USES_RE = re.compile(r'^\s*-?\s*uses:\s*([^\s#]+)', re.MULTILINE)
SHA_RE = re.compile(r'^[0-9a-f]{40}$')
DEPRECATED_ACTION_COMMITS = {
    '11d5960a326750d5838078e36cf38b85af677262',  # actions/checkout v4 generation
    'a26af69be951a213d495a4c3e4e4022e16d87065',  # actions/setup-python v5 generation
    'b9cd54a3c349d3f38e8881555d616ced269862dd',  # hashicorp/setup-terraform v3 generation
    'ea165f8d65b6e75b540449e92b4886f43607fa02',  # actions/upload-artifact v4 generation
    '0057852bfaa89a56745cba8c7296529d2fc39830',  # actions/cache v4 generation
}


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

    def test_deprecated_action_commits_are_absent(self) -> None:
        violations: list[str] = []
        for path in sorted(WORKFLOWS.glob('*.yml')) + sorted(WORKFLOWS.glob('*.yaml')):
            text = path.read_text(encoding='utf-8')
            for revision in DEPRECATED_ACTION_COMMITS:
                if revision in text:
                    violations.append(f'{path}: deprecated action commit {revision}')
        self.assertEqual(violations, [], '\n'.join(violations))

    def test_workflows_use_minimal_read_permissions_by_default(self) -> None:
        violations: list[str] = []
        for path in sorted(WORKFLOWS.glob('*.yml')) + sorted(WORKFLOWS.glob('*.yaml')):
            text = path.read_text(encoding='utf-8')
            if path.name == 'gcp-release.yml':
                if 'id-token: write' not in text or 'contents: read' not in text:
                    violations.append(f'{path}: production release must use id-token: write + contents: read')
                continue
            if 'permissions:' not in text or 'contents: read' not in text:
                violations.append(f'{path}: missing explicit contents: read permissions')
        self.assertEqual(violations, [], '\n'.join(violations))

    def test_public_data_integration_revalidates_main_after_merge(self) -> None:
        path = WORKFLOWS / 'public-data-integration.yml'
        text = path.read_text(encoding='utf-8')
        pull_request_index = text.index('  pull_request:')
        push_section = text[:pull_request_index]
        self.assertIn('  push:', push_section)
        self.assertIn('    branches:', push_section)
        self.assertRegex(push_section, r'(?m)^\s+- main\s*$')
        self.assertIn('    paths:', push_section)


if __name__ == '__main__':
    unittest.main()
