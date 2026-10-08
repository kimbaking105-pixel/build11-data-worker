#!/usr/bin/env python3
"""Validate a Tiny NNUE labeled JSONL gzip shard and its manifest."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import chess


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()
    data = Path(args.data)
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    actual_sha = sha256_file(data)
    if actual_sha != manifest.get("sha256_data"):
        raise SystemExit(f"sha256 mismatch: actual={actual_sha} manifest={manifest.get('sha256_data')}")

    count = 0
    white_stm = 0
    black_stm = 0
    family_ids = set()
    position_keys = set()
    with gzip.open(data, "rt", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            record = json.loads(line)
            required = {"fen", "score_cp", "score_mate", "stm", "ply", "game_id", "family_id", "seed", "result_stm"}
            missing = required.difference(record)
            if missing:
                raise SystemExit(f"line {line_no}: missing {sorted(missing)}")
            board = chess.Board(record["fen"])
            if record["stm"] != ("w" if board.turn == chess.WHITE else "b"):
                raise SystemExit(f"line {line_no}: stm/FEN mismatch")
            if record["stm"] == "w":
                white_stm += 1
            else:
                black_stm += 1
            if record["result_stm"] not in (-1, 0, 1):
                raise SystemExit(f"line {line_no}: invalid result_stm")
            if not -15000 <= int(record["score_cp"]) <= 15000:
                raise SystemExit(f"line {line_no}: score out of clamp range")
            family_ids.add(int(record["family_id"]))
            if "position_key" in record:
                key = str(record["position_key"])
                if key in position_keys:
                    raise SystemExit(f"line {line_no}: duplicate position_key {key}")
                position_keys.add(key)
            count += 1

    if count != int(manifest.get("records", -1)):
        raise SystemExit(f"record count mismatch: actual={count} manifest={manifest.get('records')}")
    if count == 0:
        raise SystemExit("empty shard")

    print(json.dumps({
        "ok": True,
        "records": count,
        "white_stm": white_stm,
        "black_stm": black_stm,
        "family_count": len(family_ids),
        "unique_position_keys": len(position_keys) if position_keys else None,
        "sha256": actual_sha,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
