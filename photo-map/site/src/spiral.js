export const MARKER_SPACING = 80
export const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5))

export const getSpiralOffset = (index) => {
  if (index === 0) {
    return { x: 0, y: 0 }
  }
  const radius = MARKER_SPACING * Math.sqrt(index)
  const angle = index * GOLDEN_ANGLE
  return { x: radius * Math.cos(angle), y: radius * Math.sin(angle) }
}
