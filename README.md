# build11-data-worker

Private project code is not stored here. This public repository is only a
small cloud-worker smoke test for generating self-play FEN positions with the
build1.1 baseline.

## First test

1. Open the **Actions** tab.
2. Select **test-selfplay**.
3. Click **Run workflow**.
4. Keep `positions=1000` and `movetime=5`.
5. Open the finished run and download the artifact `selfplay-test-N`.

The workflow compiles `engine_build11.cpp` on an Ubuntu GitHub runner, runs a
small self-play job, deduplicates FEN positions, and stores `positions.fen` as
an artifact. This job does not label positions yet.

## Scope

- `engine_build11.cpp` is the authoritative build1.1 baseline.
- The first workflow is deliberately small and manual.
- No build1.2 or Dynamic HCE code is used.
- Teacher labeling, shard checkpoints, and nightly scheduling are added only
after this smoke test succeeds.

Do not put API tokens, private keys, or personal files in this repository.
