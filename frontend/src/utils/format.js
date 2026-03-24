import { monthNames } from '@/data/seeds'

export function formatMonths(months) {
  if (!months || months.length === 0) return '–'
  return months.map((m) => monthNames[m]).join(', ')
}

export function buildCalendarEvents(seeds, year = new Date().getFullYear()) {
  const phaseMeta = {
    vorziehen: { label: 'Vorziehen', color: '#7c3aed' },
    direktsaat: { label: 'Direktsaat', color: '#2563eb' },
    auspflanzen: { label: 'Auspflanzen', color: '#16a34a' },
    ernte: { label: 'Ernte', color: '#ea580c' }
  }

  const events = []
  const eventIdCounts = new Map()
  seeds.forEach((seed) => {
    Object.entries(phaseMeta).forEach(([key, meta]) => {
      const months = seed[key] || []
      if (!months.length) return
      const sorted = [...months].sort((a, b) => a - b)
      const start = new Date(year, sorted[0] - 1, 1)
      const end = new Date(year, sorted[sorted.length - 1], 1)
      const baseId = `${seed.id}-${key}-${year}`
      const duplicateCount = eventIdCounts.get(baseId) || 0
      eventIdCounts.set(baseId, duplicateCount + 1)
      const eventId = duplicateCount === 0 ? baseId : `${baseId}-${duplicateCount + 1}`

      events.push({
        id: eventId,
        title: `${seed.name}${seed.sort ? ` ${seed.sort}` : ''} – ${meta.label}`,
        start: start.toISOString().slice(0, 10),
        end: end.toISOString().slice(0, 10),
        allDay: true,
        backgroundColor: meta.color,
        borderColor: meta.color,
        extendedProps: {
          phase: meta.label,
          seedId: seed.id,
          seedName: `${seed.name}${seed.sort ? ` ${seed.sort}` : ''}`
        }
      })
    })
  })
  return events
}
