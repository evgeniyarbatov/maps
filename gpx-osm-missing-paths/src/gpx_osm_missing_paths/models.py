"""Single source of truth for pipeline data: GPXSegment, Cluster, POI."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer
from shapely import wkt as shapely_wkt
from shapely.geometry import LineString, Point

BBox = tuple[float, float, float, float]


class POI(BaseModel):
    """A named OSM landmark used to generate a human-readable cluster name."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    osm_id: int
    osm_type: str  # "node" | "way"
    name: str
    category: str  # e.g. "amenity=cafe", "leisure=park"
    geometry: Point
    distance_m: float | None = None
    importance: float = 0.0

    @field_serializer("geometry")
    def _serialize_geometry(self, geom: Point, _info: Any) -> str:
        return str(geom.wkt)


class GPXSegment(BaseModel):
    """One cleaned, fixed-length chunk of a ``<trkseg>``.

    A raw ``<trkseg>`` can be a 30km run spanning dozens of streets; matching
    and OSM-coverage checks need street-sized pieces, not the whole run, so
    ``gpx_processor`` splits each cleaned trace into ~``SEGMENT_CHUNK_LENGTH_M``
    chunks before this model is ever constructed.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    segment_id: str
    source_file: Path
    original_file: str
    track_index: int
    segment_index: int
    chunk_index: int
    geometry: LineString
    length_m: float
    num_points: int
    start_time: datetime | None = None
    end_time: datetime | None = None
    bbox: BBox

    @field_serializer("geometry")
    def _serialize_geometry(self, geom: LineString, _info: Any) -> str:
        return str(geom.wkt)

    @field_serializer("source_file")
    def _serialize_source_file(self, path: Path, _info: Any) -> str:
        return str(path)


class Cluster(BaseModel):
    """A group of GPX segments believed to trace the same physical path."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    cluster_id: str
    segment_ids: list[str]
    representative_line: LineString
    num_gpx_traces: int
    avg_length_m: float
    min_length_m: float
    max_length_m: float
    total_length_m: float
    representative_length_m: float
    bbox: BBox
    source_files: list[str]

    osm_coverage_fraction: float | None = None
    is_missing: bool | None = None

    human_name: str | None = None
    slug: str | None = None
    nearby_pois: list[POI] = []
    description: str | None = None

    created_at: datetime

    @field_serializer("representative_line")
    def _serialize_geometry(self, geom: LineString, _info: Any) -> str:
        return str(geom.wkt)

    def to_meta_dict(self, **extra: Any) -> dict[str, Any]:
        """Flat dict for ``cluster_meta.json`` (stable field names for JOSM users)."""
        return {
            "human_name": self.human_name,
            "slug": self.slug,
            "num_gpx_traces": self.num_gpx_traces,
            "avg_length_m": round(self.avg_length_m, 1),
            "min_length_m": round(self.min_length_m, 1),
            "max_length_m": round(self.max_length_m, 1),
            "total_length_m": round(self.total_length_m, 1),
            "representative_length_m": round(self.representative_length_m, 1),
            "osm_coverage_fraction": (
                round(self.osm_coverage_fraction, 3)
                if self.osm_coverage_fraction is not None
                else None
            ),
            "is_missing": self.is_missing,
            "nearby_pois": [
                {"name": p.name, "category": p.category, "distance_m": round(p.distance_m or 0, 1)}
                for p in self.nearby_pois
            ],
            "source_files": self.source_files,
            "segment_ids": self.segment_ids,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            **extra,
        }

    def to_state_dict(self) -> dict[str, Any]:
        """Full round-trippable dict (geometry as WKT) for inter-step persistence."""
        return self.model_dump(mode="json")

    @classmethod
    def from_state_dict(cls, data: dict[str, Any]) -> Cluster:
        """Inverse of :meth:`to_state_dict`."""
        restored = dict(data)
        restored["representative_line"] = shapely_wkt.loads(restored["representative_line"])
        restored["nearby_pois"] = [
            {**poi, "geometry": shapely_wkt.loads(poi["geometry"])}
            for poi in restored.get("nearby_pois", [])
        ]
        return cls(**restored)


def save_clusters_state(path: Path, clusters: list[Cluster]) -> None:
    """Persist the full working set of clusters between separate CLI invocations."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([c.to_state_dict() for c in clusters], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_clusters_state(path: Path) -> list[Cluster]:
    """Load clusters previously written by :func:`save_clusters_state`."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Cluster.from_state_dict(item) for item in data]
