from __future__ import annotations

import json

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.knowledge_sync import build_obsidian_bundle,validate_obsidian_bundle


def main()->int:
    manifest=build_obsidian_bundle(); validation=validate_obsidian_bundle(manifest)
    print(json.dumps({"manifest":manifest,"validation":validation},ensure_ascii=False,indent=2))
    return 0 if validation["passed"] else 1


if __name__=="__main__": raise SystemExit(main())
