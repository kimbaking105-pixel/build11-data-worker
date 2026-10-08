#!/usr/bin/env python3
"""Create a deterministic, diverse legal opening-prefix pool.

This is not an engine match book. It is a data-generation seed pool: each line
contains a legal sequence of opening moves after which the Magic engine starts
self-play. It avoids relying on a single short list of opening lines.
"""
from __future__ import annotations

import argparse
import hashlib
import random
from pathlib import Path

import chess

ROOT_FIRST_MOVES = [
    "e2e4", "d2d4", "c2c4", "g1f3", "g2g3", "b2b3", "b1c3", "f2f4",
]


def parse_int(value: str) -> int:
    return int(value, 0)


def position_key(board: chess.Board) -> str:
    return " ".join(board.fen().split()[:4])


def move_weight(board: chess.Board, move: chess.Move, rng: random.Random) -> float:
    score = rng.random() * 4.0
    piece = board.piece_at(move.from_square)
    if move.to_square in {chess.C4, chess.D4, chess.E4, chess.F4,
                          chess.C5, chess.D5, chess.E5, chess.F5}:
        score += 5.0
    if piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP):
        score += 2.5
    if piece and piece.piece_type == chess.PAWN:
        score += 1.0
    if board.is_castling(move):
        score += 3.0
    if board.is_capture(move) or board.gives_check(move):
        score -= 4.0
    return score


def build_prefix(rng: random.Random, min_plies: int, max_plies: int) -> tuple[list[str], chess.Board]:
    board = chess.Board()
    moves: list[str] = []

    first = chess.Move.from_uci(rng.choice(ROOT_FIRST_MOVES))
    if first not in board.legal_moves:
        raise RuntimeError("invalid root opening move")
    board.push(first)
    moves.append(first.uci())

    target = rng.randint(min_plies, max_plies)
    while board.ply() < target and not board.is_game_over(claim_draw=True):
        legal = list(board.legal_moves)
        quiet = [m for m in legal if not board.is_capture(m) and not board.gives_check(m)]
        candidates = quiet or legal
        ranked = sorted(candidates, key=lambda m: move_weight(board, m, rng), reverse=True)
        # Randomly select among a reasonably good legal pool. This creates
        # variety without filling the book with early tactical blunders.
        choice_pool = ranked[: min(12, len(ranked))]
        move = rng.choice(choice_pool)
        board.push(move)
        moves.append(move.uci())
    return moves, board


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--count", type=int, default=10000)
    ap.add_argument("--seed", type=parse_int, default=0x20261008)
    ap.add_argument("--min-plies", type=int, default=8)
    ap.add_argument("--max-plies", type=int, default=12)
    args = ap.parse_args()
    if args.count <= 0 or args.min_plies < 1 or args.max_plies < args.min_plies:
        ap.error("invalid count or ply range")

    rng = random.Random(args.seed)
    seen: set[str] = set()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    attempts = 0
    with out.open("w", encoding="utf-8") as f:
        while len(seen) < args.count:
            attempts += 1
            moves, board = build_prefix(rng, args.min_plies, args.max_plies)
            key = position_key(board)
            if key in seen:
                continue
            seen.add(key)
            book_id = len(seen) - 1
            f.write(f"{book_id}\t{key}\t{' '.join(moves)}\n")
            if len(seen) % 1000 == 0:
                print(f"book_entries={len(seen)} attempts={attempts}", flush=True)

    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"written={len(seen)} attempts={attempts} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
