#!/usr/bin/env python3
"""Generate deduplicated self-play FEN positions from a UCI engine.

This is the first cloud-worker smoke tool. It generates positions only;
teacher labeling is a separate later step.
"""
from __future__ import annotations
import argparse
import random
import subprocess
import sys
import time
from pathlib import Path

import chess

OPENINGS = [
    ["e2e4", "e7e5", "g1f3", "b8c6"],
    ["e2e4", "c7c5", "g1f3", "d7d6"],
    ["e2e4", "e7e6", "d2d4", "d7d5"],
    ["e2e4", "c7c6", "d2d4", "d7d5"],
    ["d2d4", "d7d5", "c2c4", "e7e6"],
    ["d2d4", "g8f6", "c2c4", "e7e6"],
    ["c2c4", "e7e5", "g1f3", "g8f6"],
    ["g1f3", "d7d5", "d2d4", "g8f6"],
    ["b1c3", "d7d5", "e2e4", "e7e6"],
    ["b2b3", "d7d5", "c1b2", "g8f6"],
    ["c2c4", "c7c5", "g1f3", "b8c6"],
    ["e2e4", "g8f6", "e4e5", "d7d5"],
]


def build_start_position(rng: random.Random, extra_plies: int) -> chess.Board:
    """Create a varied but restrained opening position.

    The engine is deterministic at a fixed node count. Reusing only a dozen
    four-ply seeds therefore reproduces the same games. We keep the curated
    seed, then add a few quiet opening moves chosen from a small top pool. The
    subsequent moves are all made by build1.1 at the requested node budget.
    """
    board = chess.Board()
    for uci in rng.choice(OPENINGS):
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise RuntimeError(f"bad opening move {uci}")
        board.push(move)

    central = {
        chess.D4, chess.E4, chess.D5, chess.E5,
        chess.C4, chess.F4, chess.C5, chess.F5,
    }
    for _ in range(max(0, extra_plies)):
        legal = list(board.legal_moves)
        quiet = [m for m in legal if not board.is_capture(m) and not board.gives_check(m)]
        candidates = quiet or legal

        def score(move: chess.Move) -> float:
            value = rng.random() * 3.0
            piece = board.piece_at(move.from_square)
            if move.to_square in central:
                value += 4.0
            if piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                value += 2.0
            if board.is_castling(move):
                value += 3.0
            return value

        ranked = sorted(candidates, key=score, reverse=True)
        board.push(rng.choice(ranked[:min(8, len(ranked))]))
    return board


class Engine:
    def __init__(self, path: str, threads: int, hash_mb: int):
        self.p = subprocess.Popen(
            [path], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        self.send("uci")
        self.until("uciok")
        self.send(f"setoption name Threads value {threads}")
        self.send(f"setoption name Hash value {hash_mb}")
        self.ready()

    def send(self, line: str):
        assert self.p.stdin is not None
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()

    def until(self, token: str):
        assert self.p.stdout is not None
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError(f"engine exited while waiting for {token}")
            if token in line:
                return

    def ready(self):
        self.send("isready")
        self.until("readyok")

    def new_game(self):
        self.send("ucinewgame")
        self.ready()

    def move(self, board: chess.Board, movetime: int | None, nodes: int | None) -> chess.Move:
        self.send("position fen " + board.fen())
        if nodes is not None:
            self.send(f"go nodes {nodes}")
        else:
            self.send(f"go movetime {movetime}")
        assert self.p.stdout is not None
        best = None
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("engine exited during search")
            if line.startswith("bestmove"):
                fields = line.split()
                best = fields[1] if len(fields) > 1 else None
                break
        if not best or best == "0000":
            raise RuntimeError("engine returned null bestmove")
        move = chess.Move.from_uci(best)
        if move not in board.legal_moves:
            raise RuntimeError(f"engine returned illegal move {best} for {board.fen()}")
        return move

    def close(self):
        try:
            self.send("quit")
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--positions", type=int, default=1000)
    ap.add_argument("--games", type=int, default=100)
    budget = ap.add_mutually_exclusive_group(required=True)
    budget.add_argument("--movetime", type=int)
    budget.add_argument("--nodes", type=int)
    ap.add_argument("--sample-every", type=int, default=2)
    ap.add_argument("--min-ply", type=int, default=10)
    ap.add_argument("--max-plies", type=int, default=180)
    ap.add_argument("--opening-random-plies", type=int, default=6)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--hash", type=int, default=32)
    ap.add_argument("--seed", type=int, default=20261007)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    seen = set()
    games_done = 0
    stm_white = 0
    stm_black = 0
    target_white = args.positions // 2
    target_black = args.positions - target_white
    t0 = time.time()
    eng = Engine(args.engine, args.threads, args.hash)
    try:
        with open(args.out, "w", encoding="utf-8") as fo:
            for gi in range(args.games):
                if len(seen) >= args.positions:
                    break
                games_done += 1
                eng.new_game()
                board = build_start_position(rng, args.opening_random_plies)
                # Pick a random sampling phase for each game. With sample-every=2,
                # this alternates the side-to-move across games instead of
                # accidentally collecting only White-to-move positions.
                sample_offset = rng.randrange(max(1, args.sample_every))
                for ply in range(board.ply() + 1, args.max_plies + 1):
                    if board.is_game_over(claim_draw=True):
                        break
                    move = eng.move(board, args.movetime, args.nodes)
                    board.push(move)
                    if ply < args.min_ply:
                        continue
                    if (ply - args.min_ply - sample_offset) % max(1, args.sample_every):
                        continue
                    if board.is_checkmate() or board.is_stalemate() or board.is_insufficient_material():
                        continue
                    parts = board.fen().split()
                    key = " ".join(parts[:4])
                    if key in seen:
                        continue
                    # Keep the smoke/test shard exactly balanced by side to move.
                    # Once one quota is full, only accept the other side.
                    if parts[1] == "w":
                        if stm_white >= target_white:
                            continue
                    else:
                        if stm_black >= target_black:
                            continue
                    seen.add(key)
                    if parts[1] == "w":
                        stm_white += 1
                    else:
                        stm_black += 1
                    fo.write(board.fen() + "\n")
                    if stm_white >= target_white and stm_black >= target_black:
                        break
                if games_done % 10 == 0:
                    print(f"games={games_done} unique_positions={len(seen)} stm_w={stm_white} stm_b={stm_black}", flush=True)
            fo.flush()
    finally:
        eng.close()
    print(f"written={len(seen)} games={games_done} stm_w={stm_white} stm_b={stm_black} elapsed_sec={time.time()-t0:.1f}")


if __name__ == "__main__":
    main()
