"""Typer CLI entrypoint. Thin orchestration only."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from gpx_osm_missing_paths.config import get_settings

app = typer.Typer(
    name="gpx-osm",
    help="Cluster GPX traces and export JOSM bundles for paths missing from OSM.",
    no_args_is_help=True,
)
console = Console()


@app.command("osm-paths")
def osm_paths() -> None:
    """Print resolved country / city / active OSM PBF paths (debug)."""
    settings = get_settings()
    table = Table(title="OSM paths")
    table.add_column("Key")
    table.add_column("Path")
    table.add_column("Exists")
    rows = [
        ("OSM_CACHE_DIR", settings.osm_cache_dir.expanduser(), True),
        ("country_osm_path", settings.country_osm_path, settings.country_osm_path.is_file()),
        ("BOUNDARY_POLYGON", settings.boundary_polygon, settings.boundary_polygon.is_file()),
        ("city_slug", settings.city_slug, None),
        ("city_osm_pbf", settings.city_osm_pbf, settings.city_osm_pbf.is_file()),
    ]
    for key, path, exists in rows:
        if exists is None:
            table.add_row(key, str(path), "—")
        else:
            table.add_row(key, str(path), "yes" if exists else "no")
    try:
        active = settings.resolve_osm_pbf()
        table.add_row("resolve_osm_pbf()", str(active), "yes")
    except FileNotFoundError as exc:
        table.add_row("resolve_osm_pbf()", str(exc), "no")
    console.print(table)


@app.command()
def process() -> None:
    """Parse and clean GPX files (not implemented yet)."""
    console.print("[yellow]process: not implemented yet — see docs/claude-code-prompt.md[/yellow]")
    raise typer.Exit(code=1)


@app.command()
def cluster() -> None:
    """Cluster overlapping segments (not implemented yet)."""
    console.print("[yellow]cluster: not implemented yet[/yellow]")
    raise typer.Exit(code=1)


@app.command("filter-missing")
def filter_missing() -> None:
    """Keep clusters poorly covered by OSM (not implemented yet)."""
    settings = get_settings()
    pbf = settings.resolve_osm_pbf()
    console.print(f"[dim]Would filter using[/dim] {pbf}")
    console.print("[yellow]filter-missing: not implemented yet[/yellow]")
    raise typer.Exit(code=1)


@app.command()
def name() -> None:
    """Name missing clusters from POIs (not implemented yet)."""
    settings = get_settings()
    pbf = settings.resolve_osm_pbf()
    console.print(f"[dim]Would name using[/dim] {pbf}")
    console.print("[yellow]name: not implemented yet[/yellow]")
    raise typer.Exit(code=1)


@app.command()
def extract() -> None:
    """Write JOSM bundles for missing clusters (not implemented yet)."""
    settings = get_settings()
    pbf = settings.resolve_osm_pbf()
    console.print(f"[dim]Would extract using[/dim] {pbf}")
    console.print("[yellow]extract: not implemented yet[/yellow]")
    raise typer.Exit(code=1)


@app.command()
def pipeline() -> None:
    """Full pipeline (prefer ``make pipeline`` which runs city clip first)."""
    console.print("[yellow]pipeline: not implemented yet — use make pipeline after modules land[/yellow]")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
