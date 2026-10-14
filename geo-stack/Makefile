DATA_ROOT ?= $(HOME)/Documents/data
DATA_DIR  ?= $(DATA_ROOT)/geo-stack
export GEO_DATA_DIR := $(DATA_DIR)

OSM_URL       := https://download.geofabrik.de/asia/vietnam-latest.osm.pbf
SINGAPORE_URL := https://download.openstreetmap.fr/extracts/asia/singapore-latest.osm.pbf

.DEFAULT_GOAL := help
include $(HOME)/gitRepo/dotfiles/make/osm-country.mk

CITIES    := hanoi hcmc singapore
PROFILES  := foot bicycle
INSTANCES := $(foreach c,$(CITIES),$(foreach p,$(PROFILES),$(c)-$(p)))

CLIP_DIR     := $(DATA_DIR)/clip
OSRM_DIR     := $(DATA_DIR)/osrm
OVERPASS_DIR := $(DATA_DIR)/overpass

SOURCE_hanoi     := $(COUNTRY_OSM_PATH)
SOURCE_hcmc      := $(COUNTRY_OSM_PATH)
SOURCE_singapore := $(OSM_CACHE_DIR)/$(notdir $(SINGAPORE_URL))

ROUTE_hanoi     := 105.8522,21.0285;105.8342,21.0367
ROUTE_hcmc      := 106.7009,10.7769;106.6953,10.7880
ROUTE_singapore := 103.8454,1.2966;103.8303,1.3048

BBOX_hanoi     := 21.02,105.83,21.04,105.86
BBOX_hcmc      := 10.77,106.69,10.79,106.71
BBOX_singapore := 1.29,103.83,1.31,103.85

# $(1) = attempts at 5s each, $(2) = extra curl flags.
wait-http = n=0; until curl -sg $(2) -o /dev/null "$(3)"; do \
	n=$$((n+1)); [ $$n -lt $(1) ] || { echo "Timed out waiting for $(3)" >&2; exit 1; }; sleep 5; \
	done

.PHONY: help setup data run stop test

help:
	@echo "setup - fetch Vietnam + Singapore extracts, clip cities, build OSRM graphs and the Overpass import"
	@echo "run   - start OSRM (foot, bicycle) for hanoi, hcmc, singapore and Overpass; wait until they answer"
	@echo "stop  - stop all containers"
	@echo "test  - run, then one route per OSRM instance and one Overpass query per city"
	@echo ""
	@echo "Ports: hanoi 7011 foot / 7013 bicycle, hcmc 7021 / 7023, singapore 7031 / 7033, overpass 7080"
	@echo "Data goes to \$$(DATA_DIR), default ~/Documents/data/geo-stack."

setup:
	@brew bundle check --file=Brewfile >/dev/null 2>&1 || brew bundle --file=Brewfile
	@$(OSM_FETCH) "$(OSM_URL)" "$(SINGAPORE_URL)"
	@$(MAKE) --no-print-directory data

data: $(INSTANCES:%=$(OSRM_DIR)/%/region.osrm.mldgr) $(OVERPASS_DIR)/cities.osm.bz2

.SECONDEXPANSION:

$(CLIP_DIR)/%.osm.pbf: polygons/%.poly $$(SOURCE_$$*)
	@mkdir -p $(@D)
	osmium extract --overwrite -p $< -o $@ $(SOURCE_$*)

$(OSRM_DIR)/%/region.osrm.mldgr: $(CLIP_DIR)/$$(firstword $$(subst -, ,$$*)).osm.pbf
	@mkdir -p $(@D)
	cp $< $(@D)/region.osm.pbf
	docker compose run --rm osrm-build sh -c '\
		cd /osrm/$* && \
		osrm-extract -p /opt/$(lastword $(subst -, ,$*)).lua region.osm.pbf && \
		osrm-partition region.osrm && \
		osrm-customize region.osrm'

# Overpass imports only into an empty db, so new city data must wipe it.
$(OVERPASS_DIR)/cities.osm.bz2: $(CITIES:%=$(CLIP_DIR)/%.osm.pbf)
	@mkdir -p $(@D)
	osmium merge --overwrite $^ -o $@
	rm -rf $(OVERPASS_DIR)/db

run:
	@colima status >/dev/null 2>&1 || colima start
	@docker compose up -d --force-recreate --remove-orphans
	@for i in $(INSTANCES); do \
		port=$$(docker compose port $$i 5000 | cut -d: -f2); \
		$(call wait-http,24,,http://localhost:$$port/) || exit 1; \
	done
	@echo "Waiting for Overpass (first start imports the cities, up to 30 min)..."
	@$(call wait-http,360,-f,http://localhost:7080/api/interpreter?data=[out:json];out;)

stop:
	@docker compose down --remove-orphans

test: run
	@for i in $(INSTANCES); do \
		city=$${i%-*}; \
		case $$city in hanoi) r='$(ROUTE_hanoi)';; hcmc) r='$(ROUTE_hcmc)';; singapore) r='$(ROUTE_singapore)';; esac; \
		port=$$(docker compose port $$i 5000 | cut -d: -f2); \
		curl -sf "http://localhost:$$port/route/v1/foot/$$r?overview=false" | grep -q '"code":"Ok"' \
			&& echo "ok   $$i :$$port" || { echo "FAIL $$i :$$port" >&2; exit 1; }; \
	done
	@for c in $(CITIES); do \
		case $$c in hanoi) b='$(BBOX_hanoi)';; hcmc) b='$(BBOX_hcmc)';; singapore) b='$(BBOX_singapore)';; esac; \
		n=$$(curl -sfg "http://localhost:7080/api/interpreter?data=[out:json];way[highway]($$b);out%20count;" \
			| python3 -c 'import json,sys; print(json.load(sys.stdin)["elements"][0]["tags"]["ways"])'); \
		[ "$${n:-0}" -gt 0 ] && echo "ok   overpass $$c: $$n highway ways" || { echo "FAIL overpass $$c" >&2; exit 1; }; \
	done
