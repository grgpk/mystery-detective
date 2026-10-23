"""Generator eval (plan section 12): generate N cases, report first-try and final validator pass rates.

Each case costs one or more Claude Opus calls. Passing cases are written to --out for review, and with
--into-pool are added to the game's generated-case pool (DATABASE_URL).

Usage: uv run python -m scripts.generate_eval 10 --out generated/ [--concurrency 3] [--into-pool]
"""

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

from app.generation.generator import SETTINGS, GenerationResult, choose_setting, generate_case
from app.generation.pool import PostgresCasePool
from app.llm import AnthropicLLM
from app.store.repo import PostgresRepo

# Claude Opus 5.5 list prices, USD per million tokens.
PRICES = {
    "input_tokens": 4.0,
    "output_tokens": 20.0,
    "cache_read_input_tokens": 0.20,
    "cache_creation_input_tokens": 5.0,
}


def cost(usage: dict[str, int]) -> float:
    return sum(usage.get(k, 0) * price for k, price in PRICES.items()) / 1_000_000


def batch_settings(n: int, recent: list[str]) -> list[str]:
    """A distinct setting per case where possible, avoiding settings already in the pool."""
    chosen: list[str] = []
    for _ in range(n):
        chosen.append(choose_setting([*reversed(chosen), *recent]))
    return chosen


async def run(n: int, out: Path, concurrency: int, into_pool: bool) -> int:
    llm = AnthropicLLM()
    gate = asyncio.Semaphore(concurrency)
    out.mkdir(parents=True, exist_ok=True)

    repo = pool = None
    if into_pool:
        # Connect up front so each case lands in the pool as soon as it passes; stopping early loses nothing.
        repo = await PostgresRepo.connect(os.environ["DATABASE_URL"])
        pool = await PostgresCasePool.create(repo.pool)
    recent = await pool.recent_settings(len(SETTINGS)) if pool else []
    settings = batch_settings(n, recent)
    added = 0

    async def one(index: int) -> GenerationResult:
        nonlocal added
        async with gate:
            started = time.monotonic()
            result = await generate_case(llm, setting=settings[index])
            status = "PASS" if result.case else "FAIL"
            title = result.case.setting.title if result.case else result.setting
            print(
                f"[{index + 1:>2}] {status} after {len(result.attempts)} attempt(s), "
                f"{time.monotonic() - started:5.0f}s, ${cost(result.usage):.2f}  {title}",
                flush=True,
            )
            for number, attempt in enumerate(result.attempts, 1):
                for error in attempt.errors[:6]:
                    print(f"       attempt {number}: {error}", flush=True)
            if result.case:
                path = out / f"{result.case.case_id}.json"
                path.write_text(json.dumps(result.case.dump(), indent=2))
                if pool:
                    await pool.add(result.case, attempts=len(result.attempts), setting=result.setting)
                    added += 1
                    print(f"       added to the pool ({result.setting})", flush=True)
            return result

    try:
        results = await asyncio.gather(*(one(i) for i in range(n)))
    finally:
        if repo:
            await repo.close()
    passed = [r for r in results if r.case]
    first = [r for r in results if r.first_try]
    total_cost = sum(cost(r.usage) for r in results)
    error_kinds = Counter(e.split(":")[0].split(" ")[0] for r in results for a in r.attempts for e in a.errors)

    print(f"\nfirst-try pass rate: {len(first)}/{n} ({len(first) / n:.0%})")
    print(f"final pass rate:     {len(passed)}/{n} ({len(passed) / n:.0%})")
    print(f"total cost:          ${total_cost:.2f} (${total_cost / n:.2f} per case)")
    if error_kinds:
        print("most common rejections:", ", ".join(f"{k} x{v}" for k, v in error_kinds.most_common(5)))
    if into_pool:
        print(f"added {added} case(s) to the pool")
    return 0 if len(passed) == n else 1


def main() -> int:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("n", type=int, help="number of cases to generate")
    parser.add_argument("--out", type=Path, default=Path("generated"))
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--into-pool", action="store_true")
    args = parser.parse_args()
    return asyncio.run(run(args.n, args.out, args.concurrency, args.into_pool))


if __name__ == "__main__":
    sys.exit(main())
