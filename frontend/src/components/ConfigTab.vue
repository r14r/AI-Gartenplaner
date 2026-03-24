<template>
  <div class="grid-2">
    <div class="side-panel-card">
      <h3 style="margin-top:0">Ollama-Konfiguration</h3>
      <div class="small-muted" style="margin-bottom:1rem;">
        Hier legst du fest, welches Modell die Beetanalyse verwendet. Die Auswahl wird im Backend gespeichert.
      </div>

      <div class="form-grid">
        <div>
          <label class="field-label">Aktives Modell</label>
          <Select v-model="form.active_model" :options="modelOptions" optionLabel="label" optionValue="value" placeholder="Modell wählen" style="width:100%" />
        </div>

        <div>
          <label class="field-label">Analyse-Modell (optional)</label>
          <Select v-model="form.analysis_model" :options="nullableModelOptions" optionLabel="label" optionValue="value" placeholder="leer = aktives Modell" showClear style="width:100%" />
        </div>

        <div>
          <label class="field-label">Temperatur</label>
          <InputNumber v-model="form.temperature" :min="0" :max="1" :step="0.1" :minFractionDigits="1" :maxFractionDigits="1" style="width:100%" />
        </div>

        <div>
          <label class="field-label">Bevorzugte Modelle</label>
          <MultiSelect v-model="form.preferred_models" :options="modelOptions" optionLabel="label" optionValue="value" display="chip" filter style="width:100%" />
        </div>
      </div>

      <div style="margin-top:1rem;">
        <label class="field-label">Notizen</label>
        <Textarea v-model="form.notes" rows="4" style="width:100%" autoResize />
      </div>

      <div class="toolbar-row" style="margin-top:1rem; margin-bottom:0;">
        <Button label="Neu laden" icon="pi pi-refresh" severity="secondary" @click="loadAll" :loading="loading" />
        <Button label="Speichern" icon="pi pi-save" @click="save" :loading="saving" />
      </div>

      <Message v-if="message" :severity="messageSeverity" style="margin-top:1rem">{{ message }}</Message>
    </div>

    <div class="side-panel-card">
      <div style="display:flex; justify-content:space-between; gap:1rem; align-items:center; flex-wrap:wrap;">
        <div>
          <h3 style="margin:0">Modelle, Pull-Status und Cache</h3>
          <div class="small-muted">Init-Service installiert die in <code>OLLAMA_MODELS</code> definierten Modelle. Zusätzliche Modelle können hier live mit Fortschritt nachgeladen werden.</div>
        </div>
        <Button label="Aktualisieren" icon="pi pi-sync" severity="secondary" @click="loadRuntimeData" :loading="loadingModels" />
      </div>

      <div class="toolbar-row" style="margin-top:1rem;">
        <Select v-model="selectedPullModel" :options="modelOptions" optionLabel="label" optionValue="value" placeholder="Modell nachinstallieren" style="min-width:260px" />
        <Button label="Installieren" icon="pi pi-download" @click="pullModel" :disabled="!selectedPullModel" :loading="pulling" />
      </div>

      <div v-if="activeTasks.length" style="display:grid; gap:0.75rem; margin-bottom:1rem;">
        <div v-for="task in activeTasks" :key="task.id" class="meta-item">
          <div style="display:flex; justify-content:space-between; gap:1rem; align-items:center; flex-wrap:wrap;">
            <div>
              <strong>{{ task.model }}</strong>
              <div class="small-muted">{{ task.status }} · {{ task.current_status || '–' }}</div>
            </div>
            <Tag :severity="tagSeverity(task.status)" :value="`${task.progress || 0}%`" />
          </div>
          <ProgressBar :value="task.progress || 0" style="margin-top:0.75rem" />
          <div class="task-log">{{ latestLog(task) }}</div>
        </div>
      </div>

      <DataTable :value="installedModels" stripedRows size="small">
        <Column field="name" header="Modell" />
        <Column header="Größe">
          <template #body="{ data }">{{ formatBytes(data.size) }}</template>
        </Column>
        <Column field="digest" header="Digest" />
        <Column field="modified_at" header="Aktualisiert" />
      </DataTable>

      <div style="margin-top:1rem;">
        <h4 style="margin:0 0 0.5rem">Model Cache / Versioning</h4>
        <div class="small-muted" style="margin-bottom:0.75rem">Das Backend merkt sich gesehene Digests und Snapshots der installierten Modelle.</div>
        <div v-if="cacheRows.length" style="display:grid; gap:0.5rem;">
          <div v-for="row in cacheRows" :key="row.name" class="meta-item">
            <div style="display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap;">
              <strong>{{ row.name }}</strong>
              <Tag severity="secondary" :value="`${row.versions} Version(en)`" />
            </div>
            <div class="small-muted">Letzter Digest: {{ row.digest || '–' }}</div>
            <div class="small-muted">Zuletzt gesehen: {{ row.seen_at || '–' }}</div>
          </div>
        </div>
        <div v-else class="small-muted">Noch keine Cache-Daten vorhanden.</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import InputNumber from 'primevue/inputnumber'
import Message from 'primevue/message'
import MultiSelect from 'primevue/multiselect'
import ProgressBar from 'primevue/progressbar'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import { getConfig, updateConfig, getOllamaModels, pullOllamaModel, getPullTasks, getOllamaCache } from '@/api'

const loading = ref(false)
const saving = ref(false)
const loadingModels = ref(false)
const pulling = ref(false)
const installedModels = ref([])
const selectedPullModel = ref(null)
const configDefaults = ref({ models: [] })
const message = ref('')
const messageSeverity = ref('success')
const tasks = ref([])
const modelCache = ref({ versions: {}, snapshots: [] })
let pollTimer = null

const form = ref({
  active_model: '',
  analysis_model: null,
  planning_model: null,
  fallback_model: null,
  preferred_models: [],
  temperature: 0.2,
  notes: ''
})

const modelOptions = computed(() => {
  const items = new Set([
    ...configDefaults.value.models,
    ...installedModels.value.map((item) => item.name),
    ...(form.value.preferred_models || []),
    form.value.active_model,
    form.value.analysis_model,
    selectedPullModel.value,
  ].filter(Boolean))
  return Array.from(items).sort().map((name) => ({ label: name, value: name }))
})

const nullableModelOptions = computed(() => [{ label: 'Standard', value: null }, ...modelOptions.value])
const activeTasks = computed(() => tasks.value.filter((task) => ['queued', 'running'].includes(task.status)))
const cacheRows = computed(() => {
  const versions = modelCache.value.versions || {}
  return Object.entries(versions).map(([name, entries]) => {
    const last = entries[entries.length - 1] || {}
    return { name, versions: entries.length, digest: last.digest, seen_at: last.seen_at }
  }).sort((a, b) => a.name.localeCompare(b.name))
})

function latestLog(task) {
  const log = task?.log || []
  return log[log.length - 1] || 'Warte auf Updates …'
}

function tagSeverity(status) {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'warn'
  return 'secondary'
}

function formatBytes(value) {
  if (!value && value !== 0) return '–'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = value
  let unit = 0
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024
    unit += 1
  }
  return `${size.toFixed(size >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`
}

async function loadConfigData() {
  loading.value = true
  try {
    const payload = await getConfig()
    configDefaults.value = payload.defaults || { models: [] }
    form.value = {
      active_model: payload.config.active_model || '',
      analysis_model: payload.config.analysis_model || null,
      planning_model: payload.config.planning_model || null,
      fallback_model: payload.config.fallback_model || null,
      preferred_models: payload.config.preferred_models || [],
      temperature: payload.config.temperature ?? 0.2,
      notes: payload.config.notes || ''
    }
  } finally {
    loading.value = false
  }
}

async function loadRuntimeData() {
  loadingModels.value = true
  try {
    const [modelsPayload, tasksPayload, cachePayload] = await Promise.all([
      getOllamaModels(),
      getPullTasks(),
      getOllamaCache(),
    ])
    installedModels.value = modelsPayload.models || []
    tasks.value = tasksPayload.tasks || []
    modelCache.value = cachePayload || { versions: {}, snapshots: [] }
  } catch (err) {
    message.value = err.message || 'Laufzeitdaten konnten nicht geladen werden.'
    messageSeverity.value = 'error'
  } finally {
    loadingModels.value = false
  }
}

async function loadAll() {
  message.value = ''
  await Promise.all([loadConfigData(), loadRuntimeData()])
}

async function save() {
  saving.value = true
  message.value = ''
  try {
    const payload = await updateConfig({ ...form.value })
    form.value = { ...payload.config }
    message.value = 'Konfiguration gespeichert.'
    messageSeverity.value = 'success'
  } catch (err) {
    message.value = err.message || 'Konfiguration konnte nicht gespeichert werden.'
    messageSeverity.value = 'error'
  } finally {
    saving.value = false
  }
}

async function pullModel() {
  if (!selectedPullModel.value) return
  pulling.value = true
  message.value = ''
  try {
    await pullOllamaModel(selectedPullModel.value)
    message.value = `Pull für ${selectedPullModel.value} gestartet.`
    messageSeverity.value = 'success'
    await loadRuntimeData()
  } catch (err) {
    message.value = err.message || 'Modell konnte nicht installiert werden.'
    messageSeverity.value = 'error'
  } finally {
    pulling.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = window.setInterval(() => {
    loadRuntimeData()
  }, 2500)
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(async () => {
  await loadAll()
  startPolling()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>
