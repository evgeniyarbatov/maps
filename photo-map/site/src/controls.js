export const parseJumpCoordinates = (value) => {
  const [latValue, lonValue] = value.split(',').map((item) => item.trim())
  const lat = Number.parseFloat(latValue)
  const lon = Number.parseFloat(lonValue)
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    return null
  }
  return { lat, lon }
}

export const toggleSelectionState = (selectedLookup, photoId) => {
  if (selectedLookup[photoId]) {
    delete selectedLookup[photoId]
    return false
  }
  selectedLookup[photoId] = true
  return true
}

export const clearSelectionState = (selectedLookup) => {
  Object.keys(selectedLookup).forEach((photoId) => {
    delete selectedLookup[photoId]
  })
}

export const getSelectedPhotos = (photos, selectedLookup) =>
  photos.filter((photo) => selectedLookup[photo.id])

export const getDownloadPlan = (photos, selectedLookup) => {
  const selectedPhotos = getSelectedPhotos(photos, selectedLookup)
  if (!selectedPhotos.length) {
    return { type: 'none' }
  }
  if (selectedPhotos.length === 1) {
    return { type: 'single', photo: selectedPhotos[0] }
  }
  return { type: 'multi', photos: selectedPhotos }
}
