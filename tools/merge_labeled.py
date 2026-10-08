#!/usr/bin/env python3
"""Merge labeled JSONL.gz shards and deduplicate position_key globally."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def key_for(record: dict) -> str:
    if "position_key" in record:
        return str(record["position_key"])
    raw = " ".join(record["fen"].split()[:4]).encode("utf-8")
    return hashlib.blake2b(raw, digest_size=8).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()

    seen: set[str] = set()
    input_records = 0
    output_records = 0
    duplicate_records = 0
    sources = []
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with gzip.open(out_path, "wt", encoding="utf-8", compresslevel=6) as out:
        for name in args.input:
            path = Path(name)
            sources.append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            with gzip.open(path, "rt", encoding="utf-8") as src:
                for line in src:
                    input_records += 1
                    record = json.loads(line)
                    key = key_for(record)
                    if key in seen:
                        duplicate_records += 1
                        continue
                    seen.add(key)
                    record["position_key"] = key
                    out.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")
                    output_records += 1

    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    manifest = {
        "schema": "tiny-nnue-labeled-jsonl-v1-merged",
        "input_records": input_records,
        "output_records": output_records,
        "duplicate_records_removed": duplicate_records,
        "source_shards": sources,
        "sha256_data": digest,
        "data_file": out_path.name,
    }
    Path(args.manifest).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
