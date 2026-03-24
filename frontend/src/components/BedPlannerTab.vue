<template>
  <div class="grid-2">
    <div class="side-panel-card">
      <div class="toolbar-row">
        <InputText v-model="search" placeholder="Samen suchen" style="min-width:220px" />
        <Select v-model="manualSeedId" :options="seedOptions" optionLabel="label" optionValue="value" placeholder="Samen wählen" style="min-width:260px" />
        <Select v-model="manualBedId" :options="bedOptions" optionLabel="label" optionValue="value" placeholder="Beet wählen" style="min-width:180px" />
        <Button label="Hinzufügen" icon="pi pi-plus" @click="addSeedManually" :disabled="!manualSeedId || !manualBedId" />
      </div>

      <div>
        <h3 style="margin-top:0">Samenpool</h3>
        <div>
          <span
            v-for="seed in filteredSeeds"
            :key="seed.id"
            class="seed-chip"
            draggable="true"
            @dragstart="handleDragStart(seed.id)"
          >
            <i class="pi pi-seedling"></i>
            {{ seed.name }}<span v-if="seed.sort"> {{ seed.sort }}</span>
          </span>
        </div>
      </div>
    </div>

    <div>
      <div class="toolbar-row">
        <Button label="Neues Beet" icon="pi pi-plus" severity="secondary" @click="createBed" />
        <Button label="Auto-Plan via KI" icon="pi pi-sparkles" @click="runAutoPlan" :loading="autoPlanning" />
      </div>

      <div style="display:grid; gap:1rem;">
        <div v-for="bed in localBeds" :key="bed.id" class="bed-card">
          <div style="display:flex; justify-content:space-between; gap:0.75rem; align-items:flex-start; flex-wrap:wrap;">
            <div>
              <h3 style="margin:0 0 0.25rem;">{{ bed.name }}</h3>
              <div class="small-muted">Standort: {{ bed.location }} · Boden: {{ bed.soil }} · Größe: {{ bed.size }}</div>
            </div>
            <div class="toolbar-row" style="margin:0;">
              <Button label="KI prüfen" icon="pi pi-sparkles" size="small" @click="emitAnalyze(bed.id)" />
              <Button label="Leeren" icon="pi pi-trash" severity="secondary" size="small" @click="clearBed(bed.id)" />
            </div>
          </div>

          <div class="bed-dropzone" @dragover.prevent @drop="handleDrop(bed.id)">
            <div v-if="plantsForBed(bed).length === 0" class="small-muted">Samen hier hineinziehen</div>
            <div v-else>
              <span v-for="plant in plantsForBed(bed)" :key="plant.id" class="seed-chip" style="cursor:default;">
                {{ plant.name }}<span v-if="plant.sort"> {{ plant.sort }}</span>
                <i class="pi pi-times" style="cursor:pointer" @click="removeSeed(bed.id, plant.id)"></i>
              </span>
            </div>
          </div>

          <div v-if="rulesForBed(bed).positives.length">
            <strong>Passend:</strong>
            <ul class="good-list">
              <li v-for="item in rulesForBed(bed).positives" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div v-if="rulesForBed(bed).warnings.length">
            <strong>Warnungen:</strong>
            <ul class="warning-list">
              <li v-for="item in rulesForBed(bed).warnings" :key="item">{{ item }}</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import { seeds } from '@/data/seeds'
import { defaultBeds } from '@/data/defaultBeds'
import { validateBedRules } from '@/utils/bedRules'
import { autoPlan } from '@/api'

const emit = defineEmits(['update:beds', 'analyze-bed'])
const props = defineProps({
  beds: {
    type: Array,
    default: () => defaultBeds
  }
})

const localBeds = ref(JSON.parse(JSON.stringify(props.beds)))
const draggedSeedId = ref(null)
const search = ref('')
const manualSeedId = ref(null)
const manualBedId = ref(null)
const autoPlanning = ref(false)

watch(localBeds, (value) => emit('update:beds', value), { deep: true })
watch(() => props.beds, (value) => {
  localBeds.value = JSON.parse(JSON.stringify(value))
}, { deep: true })

const filteredSeeds = computed(() => {
  const q = search.value.toLowerCase()
  return seeds.filter((seed) => `${seed.name} ${seed.sort || ''}`.toLowerCase().includes(q))
})

const seedOptions = computed(() => seeds.map((seed) => ({ label: `${seed.name}${seed.sort ? ` ${seed.sort}` : ''}`, value: seed.id })))
const bedOptions = computed(() => localBeds.value.map((bed) => ({ label: bed.name, value: bed.id })))

function handleDragStart(seedId) {
  draggedSeedId.value = seedId
}

function handleDrop(bedId) {
  if (!draggedSeedId.value) return
  addSeedToBed(bedId, draggedSeedId.value)
  draggedSeedId.value = null
}

function addSeedToBed(bedId, seedId) {
  const bed = localBeds.value.find((item) => item.id === bedId)
  if (!bed) return
  if (!bed.seedIds.includes(seedId)) bed.seedIds.push(seedId)
}

function addSeedManually() {
  addSeedToBed(manualBedId.value, manualSeedId.value)
  manualSeedId.value = null
}

function plantsForBed(bed) {
  return bed.seedIds.map((id) => seeds.find((seed) => seed.id === id)).filter(Boolean)
}

function rulesForBed(bed) {
  return validateBedRules(plantsForBed(bed))
}

function removeSeed(bedId, seedId) {
  const bed = localBeds.value.find((item) => item.id === bedId)
  if (!bed) return
  bed.seedIds = bed.seedIds.filter((id) => id !== seedId)
}

function clearBed(bedId) {
  const bed = localBeds.value.find((item) => item.id === bedId)
  if (!bed) return
  bed.seedIds = []
}

function createBed() {
  const index = localBeds.value.length + 1
  localBeds.value.push({
    id: `bed-${Date.now()}`,
    name: `Beet ${index}`,
    location: 'sonnig',
    soil: 'locker',
    size: '2 x 1 m',
    seedIds: []
  })
}

function emitAnalyze(bedId) {
  emit('analyze-bed', bedId)
}

async function runAutoPlan() {
  autoPlanning.value = true
  try {
    const response = await autoPlan({ beds: localBeds.value, available_seed_ids: seeds.map((seed) => seed.id) })
    if (response?.beds?.length) {
      localBeds.value = response.beds
    }
  } finally {
    autoPlanning.value = false
  }
}
</script>
