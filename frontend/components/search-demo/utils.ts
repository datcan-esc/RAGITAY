export function formatSectionName(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toLocaleUpperCase("tr-TR"))
}

export function clampPercentage(value: number) {
  return Math.max(0, Math.min(value, 100))
}
