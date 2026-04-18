from __future__ import annotations

import asyncio
import logging

import typer
from rich.logging import RichHandler

from tikitaka.config import Settings, load_settings
from tikitaka.pipeline import Pipeline

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )


@app.command()
def run(log_level: str = typer.Option("INFO", help="DEBUG / INFO / WARNING")) -> None:
    """Start the live scanner."""
    _setup_logging(log_level)
    settings = load_settings()
    asyncio.run(_run(settings))


async def _run(settings: Settings) -> None:
    pipeline = Pipeline(settings)
    try:
        await pipeline.run()
    finally:
        await pipeline.close()


@app.command()
def backfill(
    days: int = typer.Option(7, help="Days of history to pull from the Data API"),
    log_level: str = typer.Option("INFO"),
) -> None:
    """Pull recent trades from the Data API into SQLite + Parquet archive."""
    _setup_logging(log_level)
    from tikitaka.backfill import run_backfill

    settings = load_settings()
    asyncio.run(run_backfill(settings, days=days))


@app.command()
def backtest(
    days: int = typer.Option(7),
    log_level: str = typer.Option("INFO"),
) -> None:
    """Replay archived trades through the detectors without sending alerts."""
    _setup_logging(log_level)
    from tikitaka.backtest import run_backtest

    settings = load_settings()
    asyncio.run(run_backtest(settings, days=days))


if __name__ == "__main__":
    app()
