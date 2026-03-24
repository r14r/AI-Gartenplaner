<template>
  <div class="advisor-content">
    <div class="side-panel-card">
      <div class="toolbar-row">
        <Select v-model="selectedBedId" :options="bedOptions" optionLabel="label" optionValue="value" placeholder="Beet wählen" style="min-width:220px" />
        <Button label="Analyse starten" icon="pi pi-sparkles" @click="runAnalysis" :loading="loading" :disabled="!selectedBedId" />
      </div>

      <div v-if="selectedBed">
        <h3>{{ selectedBed.name }}</h3>
        <div class="small-muted">Standort: {{ selectedBed.location }} · Boden: {{ selectedBed.soil }} · Größe: {{ selectedBed.size }}</div>
        <ul>
          <li v-for="plant in selectedPlants" :key="plant.id">{{ plant.name }}<span v-if="plant.sort"> {{ plant.sort }}</span></li>
        </ul>
      </div>
      <p v-else class="small-muted">Wähle ein Beet.</p>

      <Message v-if="error" severity="error">{{ error }}</Message>
      <Message v-if="healthMessage" severity="info" style="margin-top:1rem">{{ healthMessage }}</Message>
    </div>

    <div class="side-panel-card" v-if="taskState.id">
      <div class="meta-item">
        <div style="display:flex; justify-content:space-between; gap:1rem; align-items:center; flex-wrap:wrap;">
          <div>
            <strong>Analyse-Status</strong>
            <div class="small-muted">Task {{ taskState.id.slice(0, 8) }} · {{ taskState.statusLabel }}</div>
          </div>
          <Tag :severity="taskState.tagSeverity" :value="`${taskState.progress}%`" />
        </div>
        <ProgressBar :value="taskState.progress" style="margin-top:0.75rem" />
        <div class="small-muted" style="margin-top:0.5rem">{{ taskState.currentMessage || 'Warte auf Status ...' }}</div>
      </div>
    </div>

    <div class="side-panel-card">
      <h3 style="margin-top:0">Ablauf der Ollama-Abfrage</h3>
      <div v-if="steps.length" style="margin-bottom:1rem;">
        <div class="steps-list">
          <div v-for="(step, index) in reversedSteps" :key="`${step.timestamp}-${index}`" class="advisor-step-item">
            <div class="step-marker">{{ reversedSteps.length - index }}</div>
            <div class="step-content">
              <Tabs value="overview">
                <TabList>
                  <Tab value="overview">Überblick</Tab>
                  <Tab value="details">Details</Tab>
                </TabList>
                <TabPanels>
                  <TabPanel value="overview">
                    <div style="display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap; align-items:center;">
                      <strong>{{ step.phase }}</strong>
                      <span class="small-muted">{{ formatTimestamp(step.timestamp) }}</span>
                    </div>
                    <div>{{ step.message }}</div>
                    <div class="small-muted">Fortschritt: {{ step.progress }}%</div>
                  </TabPanel>
                  <TabPanel value="details">
                    <pre class="step-details">{{ formatStepDetails(step) }}</pre>
                  </TabPanel>
                </TabPanels>
              </Tabs>
            </div>
          </div>
        </div>
      </div>

      <div v-if="result">
        <p><strong>Score:</strong> {{ result.score }}/100 <span class="small-muted">· Modell: {{ result.model || "–" }} · Quelle: {{ result.source || "–" }}</span></p>
        <p><strong>Zusammenfassung:</strong> {{ result.summary }}</p>

        <div>
          <strong>Gute Kombinationen</strong>
          <ul class="good-list">
            <li v-for="item in result.good_pairs" :key="item.plants.join('-') + item.reason">
              {{ item.plants.join(' + ') }} — {{ item.reason }}
            </li>
          </ul>
        </div>

        <div>
          <strong>Konflikte</strong>
          <ul class="warning-list">
            <li v-for="item in result.conflicts" :key="item.plants.join('-') + item.reason">
              {{ item.plants.join(' + ') }} — {{ item.reason }}
            </li>
          </ul>
        </div>

        <div>
          <strong>Empfehlungen</strong>
          <ul>
            <li v-for="item in result.recommendations" :key="item">{{ item }}</li>
          </ul>
        </div>

        <div>
          <strong>Layout-Vorschlag</strong>
          <ul>
            <li v-for="item in result.layout_suggestion" :key="item.plant + item.position">
              {{ item.plant }} → {{ item.position }} ({{ item.reason }})
            </li>
          </ul>
        </div>
      </div>
      <p v-else class="small-muted">Noch keine Analyse ausgeführt.</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import Message from 'primevue/message'
import ProgressBar from 'primevue/progressbar'
import Tag from 'primevue/tag'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import { createAnalyzeBedTask, getAnalyzeBedTask, backendHealth } from '@/api'
import { seeds } from '@/data/seeds'

const props = defineProps({
  beds: {
    type: Array,
    default: () => []
  },
  initialBedId: {
    type: String,
    default: null
  }
})

const selectedBedId = ref(props.initialBedId)
const loading = ref(false)
const result = ref(null)
const error = ref('')
const healthMessage = ref('')
const steps = ref([])
const currentTaskId = ref(null)
let pollTimer = null

watch(() => props.initialBedId, (value) => {
  if (value) selectedBedId.value = value
})

const bedOptions = computed(() => props.beds.map((bed) => ({ label: bed.name, value: bed.id })))
const selectedBed = computed(() => props.beds.find((bed) => bed.id === selectedBedId.value) || null)
const selectedPlants = computed(() => {
  if (!selectedBed.value) return []
  return selectedBed.value.seedIds.map((id) => seeds.find((seed) => seed.id === id)).filter(Boolean)
})
const taskState = computed(() => {
  const last = steps.value[steps.value.length - 1] || null
  const status = loading.value ? 'running' : (result.value ? 'completed' : 'idle')
  return {
    id: currentTaskId.value,
    progress: last?.progress || (result.value ? 100 : 0),
    currentMessage: last?.message || '',
    statusLabel: status === 'running' ? 'läuft' : status === 'completed' ? 'abgeschlossen' : 'bereit',
    tagSeverity: status === 'running' ? 'warn' : status === 'completed' ? 'success' : 'secondary'
  }
})
const reversedSteps = computed(() => [...steps.value].reverse())

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function formatTimestamp(value) {
  if (!value) return '–'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatStepDetails(step) {
  const details = step?.details
  if (!details || typeof details !== 'object') return 'Keine zusätzlichen Details vorhanden.'
  return JSON.stringify(details, null, 2)
}

async function refreshTask() {
  if (!currentTaskId.value) return
  try {
    const payload = await getAnalyzeBedTask(currentTaskId.value)
    steps.value = payload.steps || []
    if (payload.result) result.value = payload.result
    if (payload.status === 'completed') {
      loading.value = false
      stopPolling()
    } else if (payload.status === 'failed') {
      loading.value = false
      error.value = payload.error || 'Analyse fehlgeschlagen.'
      if (payload.result) result.value = payload.result
      stopPolling()
    }
  } catch (err) {
    loading.value = false
    error.value = err.message || 'Task-Status konnte nicht geladen werden.'
    stopPolling()
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(refreshTask, 1200)
}

async function runAnalysis() {
  if (!selectedBed.value) return
  loading.value = true
  error.value = ''
  result.value = null
  steps.value = []
  currentTaskId.value = null
  try {
    const task = await createAnalyzeBedTask({
      bed_name: selectedBed.value.name,
      location: selectedBed.value.location,
      soil: selectedBed.value.soil,
      size: selectedBed.value.size,
      plants: selectedPlants.value
    })
    currentTaskId.value = task.task_id
    startPolling()
    await refreshTask()
  } catch (err) {
    loading.value = false
    error.value = err.message || 'Analyse konnte nicht gestartet werden.'
  }
}

onMounted(async () => {
  try {
    const health = await backendHealth()
    healthMessage.value = `Backend: ${health.status} · Ollama erreichbar: ${health.ollama_reachable ? 'ja' : 'nein'} · aktives Modell: ${health.active_model || '–'}`
  } catch {
    healthMessage.value = 'Backend aktuell nicht erreichbar.'
  }
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style scoped>
.advisor-content {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
}

.advisor-step-item {
  display: grid;
  grid-template-columns: 2.25rem minmax(0, 1fr);
  gap: 0.75rem;
  align-items: start;
}

.step-details {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.85rem;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 8px;
  padding: 0.75rem;
}
</style>
