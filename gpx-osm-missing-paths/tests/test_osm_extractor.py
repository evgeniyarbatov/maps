"""OSM extract helpers: bbox envelope, incomplete-relation cleanup."""

from datetime import datetime
from pathlib import Path

from shapely.geometry import LineString

from gpx_osm_missing_paths.models import Cluster
from gpx_osm_missing_paths.osm_extractor import (
    _cluster_bbox_4326,
    _strip_incomplete_relations,
)


def test_strip_incomplete_relations_keeps_complete(tmp_path: Path) -> None:
    osm = tmp_path / "test.osm"
    osm.write_text(
        """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6">
  <node id="1" lat="10.0" lon="106.0"/>
  <node id="2" lat="10.1" lon="106.1"/>
  <way id="10">
    <nd ref="1"/>
    <nd ref="2"/>
  </way>
  <relation id="100">
    <member type="way" ref="10" role="outer"/>
    <tag k="type" v="multipolygon"/>
  </relation>
  <relation id="101">
    <member type="way" ref="99999" role="outer"/>
    <tag k="type" v="boundary"/>
    <tag k="name" v="Việt Nam"/>
  </relation>
</osm>
""",
        encoding="utf-8",
    )
    removed = _strip_incomplete_relations(osm)
    assert removed == 1
    text = osm.read_text(encoding="utf-8")
    assert 'id="100"' in text
    assert 'id="101"' not in text
    assert 'id="10"' in text


def test_cluster_bbox_is_ordered() -> None:
    cluster = Cluster(
        cluster_id="c0",
        segment_ids=["s0"],
        representative_line=LineString([(106.70, 10.78), (106.701, 10.781)]),
        num_gpx_traces=1,
        avg_length_m=100.0,
        min_length_m=100.0,
        max_length_m=100.0,
        total_length_m=100.0,
        representative_length_m=100.0,
        bbox=(106.70, 10.78, 106.701, 10.781),
        source_files=["a.gpx"],
        created_at=datetime.now(),
    )
    min_lon, min_lat, max_lon, max_lat = _cluster_bbox_4326(cluster, buffer_m=50.0)
    assert min_lon < max_lon
    assert min_lat < max_lat
    assert min_lon < 106.70 < max_lon
    assert min_lat < 10.78 < max_lat
