export function validateBedRules(plants = []) {
  const warnings = []
  const positives = []

  for (let i = 0; i < plants.length; i += 1) {
    for (let j = i + 1; j < plants.length; j += 1) {
      const a = plants[i]
      const b = plants[j]
      const aName = `${a.name}${a.sort ? ` ${a.sort}` : ''}`
      const bName = `${b.name}${b.sort ? ` ${b.sort}` : ''}`

      if (a.schlechteNachbarn?.some((item) => b.name.includes(item) || item.includes(b.name)) ||
          b.schlechteNachbarn?.some((item) => a.name.includes(item) || item.includes(a.name))) {
        warnings.push(`${aName} und ${bName} gelten als problematische Nachbarn.`)
      }

      if (
        a.pflanzenfamilie &&
        b.pflanzenfamilie &&
        a.pflanzenfamilie === b.pflanzenfamilie &&
        ['Kreuzblütler', 'Nachtschattengewächse'].includes(a.pflanzenfamilie)
      ) {
        warnings.push(`${aName} und ${bName} gehören beide zu ${a.pflanzenfamilie}. Das erhöht Krankheits- und Konkurrenzrisiken.`)
      }

      if (
        a.standort &&
        b.standort &&
        a.standort !== b.standort &&
        !(a.standort.includes('sonnig') && b.standort.includes('sonnig'))
      ) {
        warnings.push(`${aName} und ${bName} haben unterschiedliche Standortansprüche.`)
      }

      if (a.guteNachbarn?.some((item) => b.name.includes(item) || item.includes(b.name)) ||
          b.guteNachbarn?.some((item) => a.name.includes(item) || item.includes(a.name))) {
        positives.push(`${aName} und ${bName} passen gut zusammen.`)
      }
    }
  }

  const zehrerCount = plants.reduce((acc, plant) => {
    acc[plant.zehrer || 'unbekannt'] = (acc[plant.zehrer || 'unbekannt'] || 0) + 1
    return acc
  }, {})

  if ((zehrerCount.stark || 0) >= 3) {
    warnings.push('Viele Starkzehrer in einem Beet. Die Nährstoffkonkurrenz ist hoch.')
  }

  return { warnings, positives }
}
