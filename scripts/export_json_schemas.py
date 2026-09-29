from __future__ import annotations

import argparse
import json
from pathlib import Path

from geowatch.contracts import CONTRACT_MODELS, json_schema_bundle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="schemas")
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for name, model in CONTRACT_MODELS.items():
        path = output / f"{name.casefold()}.schema.json"
        path.write_text(
            json.dumps(model.model_json_schema(mode="validation"), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    (output / "bundle.schema.json").write_text(
        json.dumps(json_schema_bundle(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"exported {len(CONTRACT_MODELS) + 1} schema files to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
