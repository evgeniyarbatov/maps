# Roadmap

## Why keep going

OSM almost never records how wide a way actually is — this repo answers that from data that already exists for free: the scatter of GPS traces that have crossed it. The estimate-vs-actual example (11 m estimated vs 13 m actual on one way) shows the method basically works. That's a small, contained proof that "crowd GPS noise contains real geometric signal," which is a more general finding than the single width number.

## What it opens up

Right now this measures one hand-picked way per run. The real value shows up once it can sweep a whole area's ways in one pass and produce a `way_id → width_m` table instead of a single result — because that table is the missing input for another project in this account (see below) that currently has no width data for most of its rows. Once that's wired up, the natural next question is whether width estimation is good enough on a *single* well-covered way to extend to lightly-covered ones, or whether the confidence interval collapses too fast.

## Capability this builds

Reading structured signal out of noisy, uncurated GPS data — the same underlying skill (perpendicular offset, MAD-based outlier filtering, percentile aggregation) applies anywhere consumer location data needs to be trusted more than its raw precision suggests.

