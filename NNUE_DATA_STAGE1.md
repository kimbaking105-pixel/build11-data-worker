# NNUE data stage 1

## Что загрузить в GitHub

Загрузить в репозиторий:

```text
engine_build11.cpp
engine_build11_bitboard.cpp
.github/workflows/nnue-labeled-smoke.yml
.github/workflows/nnue-labeled-shard.yml
tools/labeled_selfplay.py
tools/validate_labeled.py
```

Оригинальный `engine_build11.cpp` не изменять.

## Короткий запуск

В GitHub:

1. Открыть `Actions`.
2. Выбрать `nnue-labeled-smoke`.
3. Нажать `Run workflow`.
4. Поставить сначала:

```text
positions: 1000
games: 100
nodes: 1024
opening_random_plies: 6
```

5. Проверить artifact `nnue-labeled-smoke-*`.

Для более полезного короткого теста:

```text
positions: 10000
games: 1000
nodes: 4096
opening_random_plies: 6
```

Первые 1000 — только проверка pipeline. Это не training candidate.

## Миллионные shards

После успешного smoke запускается `nnue-labeled-shard`.

Первый shard:

```text
shard_id: 0001
positions: 1000000
games: 50000
nodes: 4096
seed: 0x20261008
opening_random_plies: 6
sample_every: 1
```

Для независимых shards менять только `shard_id` и seed, например:

```text
shard 0001: seed 0x20261008
shard 0002: seed 0x20261009
shard 0003: seed 0x2026100A
```

Официальный общий объём считается суммой shards. Каждый artifact содержит:

```text
labeled_shard_*.jsonl.gz
manifest_*.json
out-source-sha256.txt
```

## Формат записи

Каждая строка — JSON record:

```json
{
  "fen": "...",
  "score_cp": 42,
  "score_mate": 0,
  "stm": "w",
  "ply": 18,
  "game_id": 12,
  "family_id": 12,
  "seed": 539230728,
  "result_stm": 1
}
```

`score_cp` — score последнего search, `result_stm` — результат партии с точки зрения стороны, которая ходила в позиции:

```text
1  = победа стороны, которая ходила;
0  = ничья;
-1 = проигрыш стороны, которая ходила.
```

## Важное

- Данные генерируются active `engine_build11_bitboard.cpp`.
- Original control не используется для изменения файла и остаётся frozen.
- Пока генерируются labels для будущего score/WDL trainer.
- `100k` не является финальным кандидатом.
- Перед длинным обучением нужен streaming/chunked trainer.
- Не смешивать shards с разными nodes/depth без отдельного manifest и отдельного
  эксперимента.
- Сохранять SHA-256 каждого artifact и source.
