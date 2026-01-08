<script setup>
import { zipSync } from 'fflate'
import { onMounted, ref, watch } from 'vue'
import {
  clearSelectionState,
  getDownloadPlan,
  parseJumpCoordinates,
  toggleSelectionState,
} from './controls.js'
import { getSpiralOffset, MARKER_SPACING } from './spiral.js'

// Reactive state for photo data, selection, and jump input.
const photos = ref([])
const selectedLookup = ref({})
const jumpCoords = ref('')
// Layout and marker constants to keep spatial behavior consistent.
const JUMP_ZOOM = 20
const JUMP_PANE = 'jump-pane'

// Leaflet runtime references.
let map = null
let jumpMarker = null
const markers = new Map()

// Build a thumbnail marker with an optional selected style.
const makeIcon = (photo, selected) =>
  window.L.divIcon({
    className: `thumb-marker${selected ? ' is-selected' : ''}`,
    html: `<img src="${photo.thumb}" alt="${photo.name}" />`,
    iconSize: [72, 72],
    iconAnchor: [36, 36],
  })

// Refresh a single marker's icon based on selection state.
const updateMarker = (photoId) => {
  const marker = markers.get(photoId)
  const photo = photos.value.find((item) => item.id === photoId)
  if (!marker || !photo) {
    return
  }
  marker.setIcon(makeIcon(photo, Boolean(selectedLookup.value[photoId])))
}

// Group nearby markers into layout clusters in pixel space.
const buildClusters = () => {
  const clusters = []

  photos.value.forEach((photo) => {
    const point = map.latLngToLayerPoint([photo.lat, photo.lon])
    let cluster = clusters.find((item) => item.center.distanceTo(point) < MARKER_SPACING)

    if (!cluster) {
      cluster = { center: point, items: [] }
      clusters.push(cluster)
    }

    cluster.items.push({ id: photo.id, point })
    cluster.center = cluster.center.add(point).divideBy(cluster.items.length)
  })

  return clusters
}

// Apply a cluster layout to reduce marker overlap at the current zoom.
const applyLayout = () => {
  if (!map) {
    return
  }

  const clusters = buildClusters()

  clusters.forEach((cluster) => {
    if (cluster.items.length === 1) {
      const item = cluster.items[0]
      const marker = markers.get(item.id)
      if (marker) {
        marker.setLatLng(map.layerPointToLatLng(item.point))
      }
      return
    }

    cluster.items.forEach((item, index) => {
      const marker = markers.get(item.id)
      if (!marker) {
        return
      }
      const offset = getSpiralOffset(index)
      const target = window.L.point(cluster.center.x + offset.x, cluster.center.y + offset.y)
      marker.setLatLng(map.layerPointToLatLng(target))
    })
  })
}

// Toggle selection state for a photo and reflect it on the marker.
const toggleSelect = (photoId) => {
  toggleSelectionState(selectedLookup.value, photoId)
  updateMarker(photoId)
}

// Clear all selections and reset marker styling.
const clearSelection = () => {
  const selectedIds = Object.keys(selectedLookup.value)
  clearSelectionState(selectedLookup.value)
  selectedIds.forEach(updateMarker)
}

// Download one photo directly or multiple as a zip.
const downloadSelection = async () => {
  const plan = getDownloadPlan(photos.value, selectedLookup.value)
  if (plan.type === 'none') {
    return
  }

  if (plan.type === 'single') {
    const photo = plan.photo
    const link = document.createElement('a')
    link.href = photo.original
    link.download = photo.name
    document.body.appendChild(link)
    link.click()
    link.remove()
    return
  }

  const files = await Promise.all(
    plan.photos.map(async (photo) => {
      const response = await fetch(photo.original)
      const data = new Uint8Array(await response.arrayBuffer())
      return { name: photo.name, data }
    })
  )

  const payload = files.reduce((acc, file) => {
    if (file) {
      acc[file.name] = file.data
    }
    return acc
  }, {})

  const zipped = zipSync(payload, { level: 0 })
  const blob = new Blob([zipped], { type: 'application/zip' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'photos.zip'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

// Pan/zoom to an entered coordinate and drop a highlight marker.
const jumpToCoordinates = () => {
  const coords = parseJumpCoordinates(jumpCoords.value)
  if (!coords) {
    return
  }

  map.setView([coords.lat, coords.lon], JUMP_ZOOM)
  if (jumpMarker) {
    jumpMarker.setLatLng([coords.lat, coords.lon])
  } else {
    jumpMarker = window.L.circleMarker([coords.lat, coords.lon], {
      pane: JUMP_PANE,
      radius: 9,
      color: '#ffffff',
      weight: 3,
      fillColor: '#e07a26',
      fillOpacity: 1,
    }).addTo(map)
  }
  jumpMarker.bringToFront()
}

// Remove the jump marker when the input is cleared.
watch(jumpCoords, (value) => {
  if (value.trim() !== '' || !jumpMarker) {
    return
  }
  jumpMarker.remove()
  jumpMarker = null
})

// Initialize the Leaflet map, markers, and controls.
const initMap = () => {
  map = window.L.map('map', {
    zoomControl: false,
    scrollWheelZoom: true,
  }).setView([0, 0], 2)

  window.L.control.zoom({ position: 'bottomright' }).addTo(map)
  if (!map.getPane(JUMP_PANE)) {
    map.createPane(JUMP_PANE)
    map.getPane(JUMP_PANE).style.zIndex = 650
  }

  window.L
    .tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    })
    .addTo(map)

  const bounds = window.L.latLngBounds()

  photos.value.forEach((photo) => {
    const marker = window.L.marker([photo.lat, photo.lon], {
      icon: makeIcon(photo, Boolean(selectedLookup.value[photo.id])),
    }).addTo(map)

    marker.on('click', () => toggleSelect(photo.id))
    markers.set(photo.id, marker)
    bounds.extend([photo.lat, photo.lon])
  })

  if (photos.value.length) {
    map.fitBounds(bounds, { padding: [48, 48] })
  }

  applyLayout()
  map.on('zoomend', applyLayout)
}

// Load photo metadata and bring up the map on mount.
onMounted(async () => {
  try {
    const response = await fetch('/photos.json')
    const data = await response.json()
    photos.value = data.photos || []
    initMap()
  } catch (error) {
    console.error(error)
  }
})
</script>

<template>
  <div class="app">
    <div id="map"></div>
    <div class="controls">
      <!-- Quick lat/lon jump input with action buttons. -->
      <input
        v-model="jumpCoords"
        placeholder="lat,lon"
        aria-label="Latitude, Longitude"
        @keydown.enter.prevent="jumpToCoordinates"
      />
      <button
        type="button"
        class="icon"
        title="Jump"
        aria-label="Jump"
        @click="jumpToCoordinates"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M7 17L17 7M9 7h8v8" />
        </svg>
      </button>
      <button
        type="button"
        class="icon"
        title="Download"
        aria-label="Download"
        @click="downloadSelection"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 5v10M8 11l4 4 4-4M5 19h14" />
        </svg>
      </button>
      <button
        type="button"
        class="icon"
        title="Clear"
        aria-label="Clear selection"
        @click="clearSelection"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M6 6l12 12M18 6l-12 12" />
        </svg>
      </button>
    </div>
  </div>
</template>
