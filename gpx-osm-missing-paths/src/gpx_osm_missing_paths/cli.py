"""Typer CLI entrypoint. Thin orchestration only."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from gpx_osm_missing_paths.clusterer import cluster as run_cluster
from gpx_osm_missing_paths.config import get_settings
from gpx_osm_missing_paths.gpx_fetcher import fetch_gpx as run_fetch_gpx
from gpx_osm_missing_paths.gpx_processor import load_segments
from gpx_osm_missing_paths.gpx_processor import process as run_process
from gpx_osm_missing_paths.missing_filter import filter_missing as run_filter_missing
from gpx_osm_missing_paths.models import load_clusters_state
from gpx_osm_missing_paths.namer import name_clusters as run_name
from gpx_osm_missing_paths.osm_extractor import extract_clusters as run_extract

app = typer.Typer(
    name="gpx-osm",
    help="Cluster GPX traces and export JOSM bundles for paths missing from OSM.",
    no_args_is_help=True,
)
console = Console()

CLUSTERS_STATE_NAME = "clusters_state.json"


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


@app.command("fetch-gpx")
def fetch_gpx(
    lat: float | None = typer.Option(
        None, "--lat", help="Latitude of filter point (requires --lon and --radius-km)"
    ),
    lon: float | None = typer.Option(
        None, "--lon", help="Longitude of filter point (requires --lat and --radius-km)"
    ),
    radius_km: float | None = typer.Option(
        None, "--radius-km", help="Keep only tracks within this many km of --lat/--lon"
    ),
) -> None:
    """Checkout/update [private] and convert its parquet tracks into GPX_DIR."""
    given = [v is not None for v in (lat, lon, radius_km)]
    if any(given) and not all(given):
        console.print("[red]--lat, --lon and --radius-km must be given together.[/red]")
        raise typer.Exit(code=1)

    settings = get_settings()
    with console.status(f"[bold cyan]Checking out {settings.gpx_data_repo_url}..."):
        summary = run_fetch_gpx(settings, lat, lon, radius_km)

    table = Table(title="Fetch GPX summary")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Tracks seen", str(summary.tracks_seen))
    table.add_row("Tracks kept", str(summary.tracks_kept))
    table.add_row("Tracks skipped (no geometry)", str(summary.tracks_skipped_no_geometry))
    table.add_row("GPX files written", str(summary.files_written))
    console.print(table)
    if summary.files_written:
        console.print(f"[green]Wrote {summary.files_written} files → {settings.gpx_dir}[/green]")
    else:
        console.print(
            "[yellow]No tracks matched — check --lat/--lon/--radius-km or the repo contents.[/yellow]"
        )


@app.command()
def process() -> None:
    """Parse and clean every GPX file under GPX_DIR."""
    settings = get_settings()
    with console.status("[bold cyan]Parsing GPX files..."):
        segments, summary = run_process(settings)

    if summary.files_seen == 0:
        console.print(f"[yellow]No .gpx files found under {settings.gpx_dir}[/yellow]")
        raise typer.Exit(code=1)

    table = Table(title="GPX processing summary")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Files seen", str(summary.files_seen))
    table.add_row("Files failed to parse", str(summary.files_failed))
    table.add_row("Segments kept", str(summary.segments_kept))
    table.add_row("Segments dropped (too short)", str(summary.segments_dropped_short))
    table.add_row("Segments dropped (empty)", str(summary.segments_dropped_empty))
    table.add_row("Segments dropped (outside city)", str(summary.segments_dropped_outside_city))
    table.add_row("Total distance", f"{summary.total_km:.1f} km")
    console.print(table)

    if not segments:
        console.print("[yellow]No usable segments produced — nothing to cluster.[/yellow]")
        raise typer.Exit(code=1)
    console.print(f"[green]Wrote {settings.output_dir / 'segments.geojson'}[/green]")


@app.command()
def cluster() -> None:
    """Cluster overlapping segments into candidate physical paths."""
    settings = get_settings()
    segments_path = settings.output_dir / "segments.parquet"
    if not segments_path.is_file():
        console.print("[yellow]No output/segments.parquet — run `gpx-osm process` first.[/yellow]")
        raise typer.Exit(code=1)

    segments = load_segments(settings.output_dir)
    with console.status("[bold cyan]Clustering segments..."):
        clusters, summary = run_cluster(settings, segments)

    table = Table(title="Clustering summary")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Segments in", str(summary.segments_in))
    table.add_row("Clusters out", str(summary.clusters_out))
    table.add_row("Multi-trace clusters", str(summary.multi_trace_clusters))
    table.add_row("Singleton clusters (1 GPX)", str(summary.singleton_clusters))
    table.add_row("Largest cluster (GPX files)", str(summary.largest_cluster_traces))
    table.add_row("Largest cluster (segments)", str(summary.largest_cluster_segments))
    console.print(table)
    console.print(f"[green]Wrote {settings.output_dir / 'clusters_raw.geojson'}[/green]")


@app.command("filter-missing")
def filter_missing() -> None:
    """Keep only clusters poorly covered by existing OSM ways."""
    settings = get_settings()
    state_path = settings.output_dir / CLUSTERS_STATE_NAME
    if not state_path.is_file():
        console.print("[yellow]No clusters_state.json — run `gpx-osm cluster` first.[/yellow]")
        raise typer.Exit(code=1)

    pbf = settings.resolve_osm_pbf()
    clusters = load_clusters_state(state_path)
    with console.status(f"[bold cyan]Checking coverage against {pbf.name}..."):
        clusters, summary = run_filter_missing(settings, clusters)

    table = Table(title="Missing-path filter summary")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Clusters in", str(summary.clusters_in))
    table.add_row("Missing multi-trace (kept)", str(summary.missing_kept))
    table.add_row("Already covered (skipped)", str(summary.covered_skipped))
    table.add_row(
        f"Few traces (<{settings.min_cluster_traces} GPX, skipped)",
        str(summary.few_traces_skipped),
    )
    console.print(table)


@app.command()
def name() -> None:
    """Generate human-readable names for missing clusters from nearby POIs."""
    settings = get_settings()
    state_path = settings.output_dir / CLUSTERS_STATE_NAME
    if not state_path.is_file():
        console.print(
            "[yellow]No clusters_state.json — run `gpx-osm filter-missing` first.[/yellow]"
        )
        raise typer.Exit(code=1)

    pbf = settings.resolve_osm_pbf()
    clusters = load_clusters_state(state_path)
    with console.status(f"[bold cyan]Naming clusters from POIs in {pbf.name}..."):
        clusters, summary = run_name(settings, clusters)

    table = Table(title="Naming summary")
    table.add_column("Cluster")
    table.add_column("Traces", justify="right")
    table.add_column("Avg length", justify="right")
    table.add_column("Coverage", justify="right")
    missing = sorted((c for c in clusters if c.is_missing), key=lambda c: -c.num_gpx_traces)
    for c in missing:
        table.add_row(
            c.human_name or c.cluster_id,
            str(c.num_gpx_traces),
            f"{c.avg_length_m:.0f}m",
            f"{(c.osm_coverage_fraction or 0.0):.0%}",
        )
    console.print(table)
    if missing:
        console.print(
            f"[dim]{len(missing)} missing clusters "
            f"(sorted by GPX file count; open output/named_clusters.geojson on a map)[/dim]"
        )
    console.print(
        f"[dim]{summary.clusters_named} named with POI context, "
        f"{summary.clusters_without_poi} with no nearby POI[/dim]"
    )


@app.command()
def extract() -> None:
    """Write JOSM bundles (.osm + gpx/ + cluster_meta.json) for missing clusters."""
    settings = get_settings()
    state_path = settings.output_dir / CLUSTERS_STATE_NAME
    segments_path = settings.output_dir / "segments.parquet"
    if not state_path.is_file():
        console.print("[yellow]No clusters_state.json — run `gpx-osm name` first.[/yellow]")
        raise typer.Exit(code=1)

    settings.resolve_osm_pbf()
    clusters = load_clusters_state(state_path)
    segments = load_segments(settings.output_dir) if segments_path.is_file() else []
    with console.status("[bold cyan]Writing JOSM bundles..."):
        summary = run_extract(settings, clusters, segments)

    table = Table(title="JOSM bundle summary")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Bundles written", str(summary.bundles_written))
    table.add_row("Bundles failed", str(summary.bundles_failed))
    console.print(table)
    console.print(f"[green]See {settings.clusters_dir}/[/green]")


@app.command()
def pipeline() -> None:
    """Full pipeline: process -> cluster -> filter-missing -> name -> extract.

    Prefer ``make pipeline``, which also fetches raw GPX (``make gpx``) and runs
    the city PBF clip first.
    """
    process()
    cluster()
    filter_missing()
    name()
    extract()


if __name__ == "__main__":
    app()
