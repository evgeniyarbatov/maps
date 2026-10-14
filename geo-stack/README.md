# geo-stack

Shared local OSRM and Overpass for Hanoi, Ho Chi Minh City and Singapore, so projects point at `localhost` instead of running their own servers.

| City | foot | bicycle |
|---|---|---|
| Hanoi | 7011 | 7013 |
| Ho Chi Minh City | 7021 | 7023 |
| Singapore | 7031 | 7033 |

Overpass on `7080` holds all three cities.

OSRM uses the stock profiles shipped in the image. A project with its own profile or a filtered graph keeps its own OSRM.

## Run

```
make setup   # fetch extracts into ~/.cache/osm, clip cities, build graphs
make run     # start everything; first start imports Overpass
make test    # one route per instance, one Overpass query per city
make stop
```

Boundaries are in `polygons/`. Ho Chi Minh City is the merged province, so its graph is larger than the old city. Generated data lives in `~/Documents/data/geo-stack`. Rerunning `make setup` after the weekly cache refresh rebuilds only what changed. Then run `make run` to load the new data.

Needs `dotfiles` at `~/gitRepo/dotfiles` for the shared OSM cache, and Docker via colima.
