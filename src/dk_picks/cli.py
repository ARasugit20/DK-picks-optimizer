from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from dk_picks.backtest.metrics import calibration_report
from dk_picks.config import settings
from dk_picks.data import import_results_csv, import_stats_csv, ingest_odds_from_api
from dk_picks.data.ingest_espn import ingest_today_from_espn
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


@app.command("game")
def game(
    match: str = typer.Option("Thunder", "--match", "-m"),
    date: str = typer.Option(None, help="YYYYMMDD e.g. 20260528 for May 28"),
    bankroll: float = typer.Option(500.0),
):
    """Full slate: team picks + every player prop for one fixture."""
    from dk_picks.models.player_props import props_for_fixture

    init_db()
    console.print("[bold]Loading Game 6 — OKC @ Spurs...[/bold]\n")

    # Team markets
    games = ingest_today_from_espn(match_filter=match)
    console.print(f"[green]Game:[/green] {', '.join(games)}")
    sport_key = "basketball_nba"
    for market in ("h2h", "spreads", "totals"):
        try:
            train_market_model(sport_key, market)
        except ValueError:
            pass
    filt = match or "Thunder"
    rec = generate_recommendations(
        sports=["nba"],
        bankroll=bankroll,
        max_parlays=3,
        markets=["h2h", "spreads", "totals"],
        fixture_filter=filt,
        relaxed=True,
    )
    _print_all_scores(filt)
    _print_recommendations(rec, save=False, export=None)

    # Player props
    console.print("\n" + "=" * 60)
    event, picks, averages = props_for_fixture(match=match, date=date, bankroll=bankroll, relaxed=True)
    console.print(f"\n[bold]{event['name']}[/bold]")
    if event.get("odds_details"):
        console.print(f"[dim]Line: {event['odds_details']} | O/U {event.get('total')}[/dim]\n")

    if averages.empty:
        console.print("[red]Could not load player stats.[/red]")
        return

    avg_table = Table(title="Postseason averages")
    for col in ["player", "team", "min", "pts", "reb", "ast", "fg3m", "pra"]:
        avg_table.add_column(col)
    for row in averages.itertuples():
        avg_table.add_row(
            row.player[:22], row.team[:14],
            f"{row.min:.1f}", f"{row.pts:.1f}", f"{row.reb:.1f}",
            f"{row.ast:.1f}", f"{row.fg3m:.1f}", f"{row.pra:.1f}",
        )
    console.print(avg_table)

    prop_table = Table(title="Player prop picks (best side @ -110)")
    for col in ["player", "prop", "pick", "line", "proj", "prob", "edge", "stake", "conf"]:
        prop_table.add_column(col)
    for p in picks:
        prop_table.add_row(
            p.player[:20], p.prop, p.pick, f"{p.line}", f"{p.projection}",
            f"{p.prob:.1%}", f"{p.edge:+.1%}", f"${p.stake:.2f}", p.confidence,
        )
    console.print("\n")
    console.print(prop_table)


@app.command("player-props")
def player_props(
    match: str = typer.Option("Thunder", "--match", "-m", help="Team filter, e.g. Thunder"),
    date: str = typer.Option(None, help="YYYYMMDD e.g. 20260528"),
    bankroll: float = typer.Option(500.0),
    relaxed: bool = typer.Option(True, help="Show all actionable props"),
):
    """Player prop picks: points, rebounds, assists, 3PM, PRA for a fixture."""
    from dk_picks.models.player_props import props_for_fixture

    init_db()
    event, picks, averages = props_for_fixture(match=match, date=date, bankroll=bankroll, relaxed=relaxed)

    console.print(f"\n[bold]{event['name']}[/bold] (event {event['event_id']})")
    console.print("[dim]Lines estimated from postseason averages vs typical DK half-lines @ -110[/dim]\n")

    if averages.empty:
        console.print("[red]No player stats loaded.[/red]")
        raise typer.Exit(1)

    avg_table = Table(title="Postseason averages (projection base)")
    for col in ["player", "team", "min", "pts", "reb", "ast", "fg3m", "pra"]:
        avg_table.add_column(col)
    for row in averages.itertuples():
        avg_table.add_row(
            row.player[:22],
            row.team[:12],
            f"{row.min:.1f}",
            f"{row.pts:.1f}",
            f"{row.reb:.1f}",
            f"{row.ast:.1f}",
            f"{row.fg3m:.1f}",
            f"{row.pra:.1f}",
        )
    console.print(avg_table)

    if not picks:
        console.print("\n[yellow]No props cleared edge filters.[/yellow]")
        return

    prop_table = Table(title="Player prop picks")
    for col in ["player", "prop", "pick", "line", "proj", "prob", "edge", "stake", "conf"]:
        prop_table.add_column(col)
    for p in picks:
        prop_table.add_row(
            p.player[:20],
            p.prop,
            p.pick,
            f"{p.line}",
            f"{p.projection}",
            f"{p.prob:.1%}",
            f"{p.edge:+.1%}",
            f"${p.stake:.2f}",
            p.confidence,
        )
    console.print("\n")
    console.print(prop_table)


@app.command("today")
def today(
    match: str = typer.Option(
        None,
        "--match",
        "-m",
        help="Filter fixture, e.g. Thunder, Spurs, or OKC",
    ),
    bankroll: float = typer.Option(500.0),
    save: bool = typer.Option(False),
    relaxed: bool = typer.Option(
        False,
        help="Lower edge filters and show all model scores (for testing)",
    ),
):
    """Ingest today's NBA lines from ESPN (DK) and print picks for one fixture."""
    init_db()
    games = ingest_today_from_espn(match_filter=match)
    console.print(f"[green]Loaded:[/green] {', '.join(games)}")
    sport_key = "basketball_nba"
    for market in ("h2h", "spreads", "totals"):
        try:
            train_market_model(sport_key, market)
        except ValueError as e:
            console.print(f"[yellow]Skip train {market}: {e}[/yellow]")
    filt = match or games[0].split(" at ")[0].split()[-1]
    rec = generate_recommendations(
        sports=["nba"],
        bankroll=bankroll,
        max_parlays=5,
        markets=["h2h", "spreads", "totals"],
        fixture_filter=filt,
        relaxed=relaxed,
    )
    _print_all_scores(filt)
    _print_recommendations(rec, save=save, export=None)


def _print_all_scores(fixture_filter: str) -> None:
    from dk_picks.models.predict import predict_proba

    console.print("\n[bold]Model scores (all markets):[/bold]")
    for market in ("h2h", "spreads", "totals"):
        try:
            df = predict_proba("basketball_nba", market)
        except FileNotFoundError:
            continue
        mask = (
            df["home_team"].str.contains(fixture_filter, case=False, na=False)
            | df["away_team"].str.contains(fixture_filter, case=False, na=False)
        )
        df = df[mask]
        for row in df.itertuples():
            pt = f" {row.point}" if getattr(row, "point", 0) else ""
            console.print(
                f"  [{market}] {row.outcome}{pt}: "
                f"P(win)={row.model_prob:.1%} fair={row.fair_prob:.1%} edge={row.edge:+.1%} "
                f"EV={row.ev:+.3f} (${row.price_american:+d})"
            )


def _print_recommendations(rec: dict, save: bool, export: Path | None) -> None:
    singles = rec["singles"]
    if not singles.empty:
        table = Table(title="Top singles (edge-filtered)")
        for col in ["home_team", "away_team", "outcome", "market", "model_prob", "edge", "ev", "stake"]:
            table.add_column(col)
        for row in singles.head(15).itertuples():
            table.add_row(
                str(row.home_team)[:14],
                str(row.away_team)[:14],
                str(row.outcome)[:18],
                str(row.market),
                f"{row.model_prob:.3f}",
                f"{row.edge:.3f}",
                f"{row.ev:.3f}",
                f"${row.stake:.2f}",
            )
        console.print(table)
    else:
        console.print("[yellow]No singles passed edge/confidence filters for this fixture.[/yellow]")
        console.print("[dim]Try lowering min_single_edge in config/thresholds.yaml for testing.[/dim]")

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


@app.command("recommend")
def recommend(
    bankroll: float = typer.Option(None),
    max_parlays: int = typer.Option(10),
    save: bool = typer.Option(False, help="Persist picks to DB"),
    export: Path = typer.Option(None, help="Write JSON to path"),
):
    rec = generate_recommendations(bankroll=bankroll, max_parlays=max_parlays)
    _print_recommendations(rec, save=save, export=export)


@app.command("report")
def report():
    r = calibration_report()
    console.print(r)


if __name__ == "__main__":
    app()
