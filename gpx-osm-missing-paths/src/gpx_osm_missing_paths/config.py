"""Pipeline settings. OSM data comes from the shared country cache + city poly clip."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _expand(path: Path) -> Path:
    return path.expanduser().resolve()


class Settings(BaseSettings):
    """All tunable paths and parameters (env / .env).

    Country PBF is **not** downloaded by this project. It is expected under
    ``OSM_CACHE_DIR`` (default ``~/.cache/osm``), populated by dotfiles
    ``fetch-osm`` / launchd ``com.arbatov.fetch-osm``. City scope is a local
    ``osmium extract`` clip of that PBF with ``BOUNDARY_POLYGON`` (default
    ``osm/hcm.poly``). Switch country via ``OSM_URL`` / ``OSM_COUNTRY_FILE``
    and city via ``BOUNDARY_POLYGON`` (any osmconvert ``.poly``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Shared country cache (dotfiles)
    osm_cache_dir: Path = Field(default=Path("~/.cache/osm"))
    osm_country_file: str = Field(default="vietnam-latest.osm.pbf")
    osm_url: str = Field(
        default="https://download.geofabrik.de/asia/vietnam-latest.osm.pbf",
        description="Geofabrik (or other) URL; basename must match osm_country_file when using make country.",
    )

    # City boundary poly is committed input, stays in-repo under osm/.
    boundary_polygon: Path = Field(default=Path("osm/hcm.poly"))
    # Generated city PBF/XML clip + all pipeline working data live outside the repo.
    osm_dir: Path = Field(default=Path("~/Documents/data/gpx-osm-missing-paths/osm"))
    # Explicit override after make city; empty → derive from boundary basename
    osm_pbf_path: Path | None = Field(default=None)

    gpx_dir: Path = Field(default=Path("~/Documents/data/gpx-osm-missing-paths/gpx"))
    clusters_dir: Path = Field(default=Path("~/Documents/data/gpx-osm-missing-paths/clusters"))
    output_dir: Path = Field(default=Path("~/Documents/data/gpx-osm-missing-paths/output"))

    # Raw GPX source: github.com/evgeniyarbatov/gpx-data, per-city GeoParquet exports.
    # Checked out under GPX_DATA_ROOT/<repo name> — kept outside the project directory
    # since it's the mapper's personal activity history, not project data.
    gpx_data_repo_url: str = Field(default="https://github.com/evgeniyarbatov/gpx-data.git")
    gpx_data_root: Path = Field(default=Path("~/Documents/data"))

    min_segment_length_m: float = 25.0
    # Long runs (up to ~30km) cover many streets; only a fraction of any one run is
    # ever the same physical path as another. Chunking to street-sized pieces before
    # clustering/coverage checks lets a genuinely missing 500m alley get flagged even
    # when it sits inside an otherwise well-covered 20km recording.
    segment_chunk_length_m: float = 750.0
    simplify_tolerance_m: float = 4.0
    cluster_buffer_m: float = 50.0
    poi_search_radius_m: float = 50.0
    min_poi_distance_m: float = 10.0

    # Clustering: same physical stretch (urban GPS ~5–15m noise).
    # Midpoint search radius for candidate pairs (meters, UTM).
    cluster_midpoint_max_m: float = 200.0
    # Buffer when measuring how much of the shorter line sits near the longer one.
    cluster_overlap_buffer_m: float = 20.0
    # Min fraction of the shorter line that must fall inside that buffer.
    cluster_overlap_fraction: float = 0.45
    # Max mean point-to-line distance (m) for two segments to match.
    cluster_mean_distance_m: float = 20.0
    # JOSM bundles / missing map: require this many distinct GPX files.
    # One-off chunks are noise for a tired mapper; raise to 3 for a tighter list.
    min_cluster_traces: int = 2

    existing_path_match_buffer_m: float = 12.0
    missing_coverage_threshold: float = 0.45

    @field_validator(
        "osm_cache_dir",
        "boundary_polygon",
        "osm_dir",
        "gpx_dir",
        "clusters_dir",
        "output_dir",
        "gpx_data_root",
        mode="before",
    )
    @classmethod
    def _coerce_path(cls, value: object) -> Path:
        if value is None or value == "":
            raise ValueError("path setting must not be empty")
        return Path(str(value)).expanduser()

    @field_validator("osm_pbf_path", mode="before")
    @classmethod
    def _coerce_optional_path(cls, value: object) -> Path | None:
        if value is None or value == "":
            return None
        return Path(str(value)).expanduser()

    @property
    def country_osm_path(self) -> Path:
        """Absolute path to the country-level PBF in the shared cache."""
        return _expand(self.osm_cache_dir / self.osm_country_file)

    @property
    def city_slug(self) -> str:
        """Filesystem stem of the city poly (e.g. ``hcm`` from ``osm/hcm.poly``)."""
        return self.boundary_polygon.stem

    @property
    def city_osm_pbf(self) -> Path:
        """Clipped city extract produced by ``make city``."""
        return (self.osm_dir / f"{self.city_slug}.osm.pbf").resolve()

    @property
    def city_osm_xml(self) -> Path:
        """XML twin of the city extract (optional; osmium cat)."""
        return (self.osm_dir / f"{self.city_slug}.osm").resolve()

    @property
    def gpx_data_repo_dir(self) -> Path:
        """Local checkout of ``gpx_data_repo_url`` under ``gpx_data_root`` (default ``~/Documents/data/gpx-data``)."""
        name = self.gpx_data_repo_url.rstrip("/").rsplit("/", 1)[-1]
        if name.endswith(".git"):
            name = name[: -len(".git")]
        return _expand(self.gpx_data_root) / name

    def resolve_osm_pbf(self) -> Path:
        """PBF used by filter / name / per-cluster extracts.

        Preference: explicit ``OSM_PBF_PATH`` → city clip → country cache.
        Raises ``FileNotFoundError`` with a short how-to if nothing exists.
        """
        candidates: list[Path] = []
        if self.osm_pbf_path is not None:
            candidates.append(_expand(self.osm_pbf_path))
        candidates.append(self.city_osm_pbf)
        candidates.append(self.country_osm_path)

        for path in candidates:
            if path.is_file():
                return path

        raise FileNotFoundError(
            "No OSM PBF found. Expected one of:\n"
            f"  - OSM_PBF_PATH={self.osm_pbf_path}\n"
            f"  - city extract: {self.city_osm_pbf}  (run: make city)\n"
            f"  - country cache: {self.country_osm_path}  "
            "(run: make country, or wait for launchd com.arbatov.fetch-osm)\n"
            f"Boundary poly: {self.boundary_polygon}"
        )


def get_settings() -> Settings:
    """Load settings from environment and optional ``.env``."""
    return Settings()
