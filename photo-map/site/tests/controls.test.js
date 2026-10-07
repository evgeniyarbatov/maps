import assert from 'node:assert/strict'
import test from 'node:test'

import {
  clearSelectionState,
  getDownloadPlan,
  getSelectedPhotos,
  parseJumpCoordinates,
  toggleSelectionState,
} from '../src/controls.js'

const samplePhotos = [
  { id: 'p1', name: 'one.jpg', original: '/one.jpg' },
  { id: 'p2', name: 'two.jpg', original: '/two.jpg' },
]

test('parseJumpCoordinates returns null for invalid input', () => {
  assert.equal(parseJumpCoordinates(''), null)
  assert.equal(parseJumpCoordinates('abc,123'), null)
  assert.equal(parseJumpCoordinates('12.5,'), null)
})

test('parseJumpCoordinates parses lat/lon values', () => {
  assert.deepEqual(parseJumpCoordinates('34.05, -118.25'), {
    lat: 34.05,
    lon: -118.25,
  })
})

test('toggleSelectionState updates lookup and returns state', () => {
  const selected = {}
  assert.equal(toggleSelectionState(selected, 'p1'), true)
  assert.deepEqual(selected, { p1: true })
  assert.equal(toggleSelectionState(selected, 'p1'), false)
  assert.deepEqual(selected, {})
})

test('clearSelectionState removes all selections', () => {
  const selected = { p1: true, p2: true }
  clearSelectionState(selected)
  assert.deepEqual(selected, {})
})

test('getSelectedPhotos filters photos by lookup', () => {
  const selected = { p2: true }
  assert.deepEqual(getSelectedPhotos(samplePhotos, selected), [samplePhotos[1]])
})

test('getDownloadPlan returns none when empty', () => {
  assert.deepEqual(getDownloadPlan(samplePhotos, {}), { type: 'none' })
})

test('getDownloadPlan returns single when one selected', () => {
  const plan = getDownloadPlan(samplePhotos, { p1: true })
  assert.equal(plan.type, 'single')
  assert.deepEqual(plan.photo, samplePhotos[0])
})

test('getDownloadPlan returns multi when multiple selected', () => {
  const plan = getDownloadPlan(samplePhotos, { p1: true, p2: true })
  assert.equal(plan.type, 'multi')
  assert.deepEqual(plan.photos, samplePhotos)
})
