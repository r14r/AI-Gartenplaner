<template>
  <div class="grid-2">
    <div class="side-panel-card">
      <div class="toolbar-row">
        <InputText v-model="search" placeholder="Sorte suchen" style="min-width: 220px" />
        <Select
          v-model="selectedCategory"
          :options="categoryOptions"
          optionLabel="label"
          optionValue="value"
          showClear
          placeholder="Kategorie"
          style="min-width: 180px"
        />
      </div>

      <DataTable :value="filteredSeeds" paginator :rows="10" stripedRows responsiveLayout="scroll" selectionMode="single" @rowSelect="onRowSelect">
        <Column field="name" header="Name" />
        <Column field="sort" header="Sorte" />
        <Column field="category" header="Kategorie" />
        <Column header="Vorziehen">
          <template #body="slotProps">{{ formatMonths(slotProps.data.vorziehen) }}</template>
        </Column>
        <Column header="Direktsaat">
          <template #body="slotProps">{{ formatMonths(slotProps.data.direktsaat) }}</template>
        </Column>
        <Column header="Ernte">
          <template #body="slotProps">{{ formatMonths(slotProps.data.ernte) }}</template>
        </Column>
      </DataTable>
    </div>

    <div class="side-panel-card">
      <h3 style="margin-top:0">Samenpäckchen – Details</h3>
      <div v-if="selectedSeed" class="detail-grid">
        <div class="meta-item"><strong>Name</strong><div>{{ selectedSeed.name }}</div></div>
        <div class="meta-item"><strong>Sorte</strong><div>{{ selectedSeed.sort || '–' }}</div></div>
        <div class="meta-item"><strong>Kategorie</strong><div>{{ selectedSeed.category }}</div></div>
        <div class="meta-item"><strong>Unterkategorie</strong><div>{{ selectedSeed.subcategory }}</div></div>
        <div class="meta-item"><strong>Vorziehen</strong><div>{{ formatMonths(selectedSeed.vorziehen) }}</div></div>
        <div class="meta-item"><strong>Direktsaat</strong><div>{{ formatMonths(selectedSeed.direktsaat) }}</div></div>
        <div class="meta-item"><strong>Auspflanzen</strong><div>{{ formatMonths(selectedSeed.auspflanzen) }}</div></div>
        <div class="meta-item"><strong>Ernte</strong><div>{{ formatMonths(selectedSeed.ernte) }}</div></div>
        <div class="meta-item"><strong>Saattiefe</strong><div>{{ selectedSeed.saattiefe }}</div></div>
        <div class="meta-item"><strong>Standort</strong><div>{{ selectedSeed.standort }}</div></div>
        <div class="meta-item"><strong>Wasserbedarf</strong><div>{{ selectedSeed.wasserbedarf }}</div></div>
        <div class="meta-item"><strong>Zehrer</strong><div>{{ selectedSeed.zehrer }}</div></div>
        <div class="meta-item"><strong>Wuchsform</strong><div>{{ selectedSeed.wuchsform }}</div></div>
        <div class="meta-item"><strong>Pflanzenfamilie</strong><div>{{ selectedSeed.pflanzenfamilie }}</div></div>
        <div class="meta-item"><strong>Gute Nachbarn</strong><div>{{ selectedSeed.guteNachbarn?.join(', ') || '–' }}</div></div>
        <div class="meta-item"><strong>Schlechte Nachbarn</strong><div>{{ selectedSeed.schlechteNachbarn?.join(', ') || '–' }}</div></div>
      </div>
      <p v-if="selectedSeed" class="small-muted" style="margin-top:1rem">{{ selectedSeed.hinweise }}</p>
      <p v-else class="small-muted">Wähle links einen Datensatz aus.</p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import { seeds } from '@/data/seeds'
import { formatMonths } from '@/utils/format'

const search = ref('')
const selectedCategory = ref(null)
const selectedSeed = ref(seeds[0] || null)

const categoryOptions = computed(() => [...new Set(seeds.map((seed) => seed.category))].map((item) => ({ label: item, value: item })))

const filteredSeeds = computed(() => {
  return seeds.filter((seed) => {
    const query = `${seed.name} ${seed.sort || ''} ${seed.category}`.toLowerCase()
    const matchesSearch = query.includes(search.value.toLowerCase())
    const matchesCategory = !selectedCategory.value || seed.category === selectedCategory.value
    return matchesSearch && matchesCategory
  })
})

function onRowSelect(event) {
  selectedSeed.value = event.data
}
</script>
