import assert from 'node:assert/strict'
import test from 'node:test'

import { GOLDEN_ANGLE, MARKER_SPACING, getSpiralOffset } from '../src/spiral.js'

test('getSpiralOffset returns origin for index 0', () => {
  assert.deepEqual(getSpiralOffset(0), { x: 0, y: 0 })
})

test('getSpiralOffset follows the golden-angle spiral', () => {
  const offset = getSpiralOffset(1)
  const radius = MARKER_SPACING
  const expectedX = radius * Math.cos(GOLDEN_ANGLE)
  const expectedY = radius * Math.sin(GOLDEN_ANGLE)

  assert.ok(Math.abs(offset.x - expectedX) < 1e-9)
  assert.ok(Math.abs(offset.y - expectedY) < 1e-9)
})

test('getSpiralOffset uses sqrt radius for index 2', () => {
  const offset = getSpiralOffset(2)
  const radius = MARKER_SPACING * Math.sqrt(2)
  const expectedX = radius * Math.cos(2 * GOLDEN_ANGLE)
  const expectedY = radius * Math.sin(2 * GOLDEN_ANGLE)

  assert.ok(Math.abs(offset.x - expectedX) < 1e-9)
  assert.ok(Math.abs(offset.y - expectedY) < 1e-9)
})

test('getSpiralOffset radius increases from 1 to 2', () => {
  const offsetOne = getSpiralOffset(1)
  const offsetTwo = getSpiralOffset(2)
  const radiusOne = Math.hypot(offsetOne.x, offsetOne.y)
  const radiusTwo = Math.hypot(offsetTwo.x, offsetTwo.y)

  assert.ok(radiusTwo > radiusOne)
})
