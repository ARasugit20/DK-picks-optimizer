from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from dk_picks.backtest.metrics import calibration_report
from dk_picks.config import settings
from dk_picks.data import import_results_csv, import_stats_csv, ingest_odds_from_api
from dk_picks.db import init_db
from dk_picks.models.train import train_market_model
from dk_picks.recommend import export_json, generate_recommendations, persist_recommendations

app = typer.Typer(help="DraftKings ML pick optimizer")
console = Console()


@app.command("init-db")
def init_db_cmd():
    init_db()
    console.print(f"[green]Database ready:[/green] {settings.db_path}")


@app.command("ingest-odds")
def ingest_odds(sport: str = typer.Option("basketball_nba", help="Sport key or alias nba/nfl")):
    alias = {"nba": "basketball_nba", "nfl": "americanfootball_nfl", "mlb": "baseball_mlb"}
    key = alias.get(sport.lower(), sport)
    n = ingest_odds_from_api(key)
    console.print(f"[green]Ingested {n} odds rows for {key}[/green]")


@app.command("import-stats")
def import_stats(
    path: Path = typer.Argument(..., exists=True),
    sport: str = typer.Option(..., help="Sport label, e.g. basketball_nba"),
):
    n = import_stats_csv(path, sport)
    console.print(f"[green]Imported {n} team stat rows[/green]")


@app.command("import-results")
def import_results(path: Path = typer.Argument(..., exists=True)):
    n = import_results_csv(path)
    console.print(f"[green]Updated {n} pick results[/green]")


@app.command("train")
def train(
    sport: str = typer.Option("basketball_nba"),
    market: str = typer.Option("h2h"),
):
    alias = {"nba": "basketball_nba", "nfl": "americanfootball_nfl"}
    key = alias.get(sport.lower(), sport)
    out = train_market_model(key, market)
    console.print(f"[green]Model saved:[/green] {out}")


@app.command("recommend")
def recommend(
    bankroll: float = typer.Option(None),
    max_parlays: int = typer.Option(10),
    save: bool = typer.Option(False, help="Persist picks to DB"),
    export: Path = typer.Option(None, help="Write JSON to path"),
):
    rec = generate_recommendations(bankroll=bankroll, max_parlays=max_parlays)
    singles = rec["singles"]

    if not singles.empty:
        table = Table(title="Top singles (edge-filtered)")
        for col in ["sport", "outcome", "market", "model_prob", "edge", "ev", "stake"]:
            table.add_column(col)
        for row in singles.head(15).itertuples():
            table.add_row(
                str(row.sport)[:12],
                str(row.outcome)[:20],
                str(row.market),
                f"{row.model_prob:.3f}",
                f"{row.edge:.3f}",
                f"{row.ev:.3f}",
                f"${row.stake:.2f}",
            )
        console.print(table)
    else:
        console.print("[yellow]No singles passed filters. Ingest odds, import stats, train models.[/yellow]")

    console.print(f"\n[bold]Parlays ({len(rec['parlays'])}):[/bold]")
    for i, p in enumerate(rec["parlays"], 1):
        console.print(f"  {i}. edge={p['edge']:.3f} joint_p={p['joint_prob']:.3f} stake=${p['stake']}")
        for leg in p["legs"]:
            console.print(f"     - {leg}")

    if save:
        n = persist_recommendations(rec)
        console.print(f"[green]Logged {n} pick rows[/green]")
    if export:
        export_json(rec, export)
        console.print(f"[green]Exported to {export}[/green]")


@app.command("report")
def report():
    r = calibration_report()
    console.print(r)


if __name__ == "__main__":
    app()
