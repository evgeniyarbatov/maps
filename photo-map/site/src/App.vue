<script setup>
import { zipSync } from 'fflate'
import { onMounted, ref, watch } from 'vue'

const photos = ref([])
const selectedLookup = ref({})
const jumpCoords = ref('')
const JUMP_ZOOM = 17
const JUMP_PANE = 'jump-pane'

let map = null
let jumpMarker = null
const markers = new Map()

const makeIcon = (photo, selected) =>
  window.L.divIcon({
    className: `thumb-marker${selected ? ' is-selected' : ''}`,
    html: `<img src="${photo.thumb}" alt="${photo.name}" />`,
    iconSize: [72, 72],
    iconAnchor: [36, 36],
  })

const updateMarker = (photoId) => {
  const marker = markers.get(photoId)
  const photo = photos.value.find((item) => item.id === photoId)
  if (!marker || !photo) {
    return
  }
  marker.setIcon(makeIcon(photo, Boolean(selectedLookup.value[photoId])))
}

const toggleSelect = (photoId) => {
  if (selectedLookup.value[photoId]) {
    delete selectedLookup.value[photoId]
  } else {
    selectedLookup.value[photoId] = true
  }
  updateMarker(photoId)
}

const clearSelection = () => {
  Object.keys(selectedLookup.value).forEach((photoId) => {
    delete selectedLookup.value[photoId]
    updateMarker(photoId)
  })
}

const downloadSelection = async () => {
  const selectedIds = Object.keys(selectedLookup.value)
  if (!selectedIds.length) {
    return
  }

  if (selectedIds.length === 1) {
    const photo = photos.value.find((item) => item.id === selectedIds[0])
    if (!photo) {
      return
    }
    const link = document.createElement('a')
    link.href = photo.original
    link.download = photo.name
    document.body.appendChild(link)
    link.click()
    link.remove()
    return
  }

  const files = await Promise.all(
    selectedIds.map(async (photoId) => {
      const photo = photos.value.find((item) => item.id === photoId)
      if (!photo) {
        return null
      }
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

const jumpToCoordinates = () => {
  const [latValue, lonValue] = jumpCoords.value.split(',').map((item) => item.trim())
  const lat = Number.parseFloat(latValue)
  const lon = Number.parseFloat(lonValue)
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    return
  }

  map.setView([lat, lon], JUMP_ZOOM)
  if (jumpMarker) {
    jumpMarker.setLatLng([lat, lon])
  } else {
    jumpMarker = window.L.circleMarker([lat, lon], {
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

watch(jumpCoords, (value) => {
  if (value.trim() !== '' || !jumpMarker) {
    return
  }
  jumpMarker.remove()
  jumpMarker = null
})

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
}

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
      <input v-model="jumpCoords" placeholder="lat,lon" aria-label="Latitude, Longitude" />
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
