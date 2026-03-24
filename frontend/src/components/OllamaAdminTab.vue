<template>
  <div class="grid-2 admin-grid">
    <div class="side-panel-card">
      <div class="toolbar-row toolbar-space-between" style="margin-top:0">
        <div>
          <h3 style="margin:0">Ollama Admin</h3>
          <div class="small-muted">Modelle verwalten, Details anzeigen, kopieren, löschen und Testabfragen mit Statusschritten ausführen.</div>
        </div>
        <Tag :severity="health.reachable ? 'success' : 'danger'" :value="health.reachable ? 'online' : 'offline'" />
      </div>

      <div class="meta-grid" style="margin-top:1rem; margin-bottom:1rem;">
        <div class="meta-item">
          <div class="small-muted">Default-Modell</div>
          <strong>{{ modelsPayload.default_model || '–' }}</strong>
        </div>
        <div class="meta-item">
          <div class="small-muted">Installierte Modelle</div>
          <strong>{{ models.length }}</strong>
        </div>
        <div class="meta-item">
          <div class="small-muted">Pull-Tasks aktiv</div>
          <strong>{{ activePullTasks.length }}</strong>
        </div>
      </div>

      <div class="toolbar-row">
        <Select v-model="selectedCuratedModel" :options="curatedModelOptions" optionLabel="label" optionValue="value" placeholder="Kuratiertes Modell" style="min-width: 260px;" />
        <InputText v-model="customModelName" placeholder="oder Modellname frei eingeben" style="min-width: 240px; flex:1;" />
        <Button label="Installieren" icon="pi pi-download" @click="installModel" :loading="installing" />
        <Button label="Neu laden" icon="pi pi-refresh" severity="secondary" @click="loadAll" :loading="loading" />
      </div>

      <DataTable :value="models" stripedRows size="small" dataKey="name" style="margin-top:1rem;">
        <Column field="name" header="Modell" />
        <Column header="Größe">
          <template #body="{ data }">{{ formatBytes(data.size) }}</template>
        </Column>
        <Column header="Familie">
          <template #body="{ data }">{{ data.details?.family || '–' }}</template>
        </Column>
        <Column header="Params">
          <template #body="{ data }">{{ data.details?.parameter_size || '–' }}</template>
        </Column>
        <Column header="Quant.">
          <template #body="{ data }">{{ data.details?.quantization_level || '–' }}</template>
        </Column>
        <Column header="Default">
          <template #body="{ data }">
            <Tag v-if="data.is_default" severity="contrast" value="aktiv" />
            <span v-else>–</span>
          </template>
        </Column>
        <Column header="Aktionen" style="min-width: 18rem;">
          <template #body="{ data }">
            <div class="inline-actions">
              <Button label="Details" size="small" severity="secondary" @click="openDetails(data.name)" />
              <Button label="Kopie" size="small" severity="help" @click="openCopy(data.name)" />
              <Button label="Löschen" size="small" severity="danger" outlined @click="removeModel(data.name)" />
            </div>
          </template>
        </Column>
      </DataTable>

      <div style="margin-top:1rem;" v-if="activePullTasks.length">
        <h4 style="margin:0 0 0.5rem">Installations-Status</h4>
        <div v-for="task in activePullTasks" :key="task.id" class="meta-item" style="margin-bottom:0.75rem;">
          <div class="toolbar-row toolbar-space-between" style="margin-top:0; margin-bottom:0.5rem;">
            <div>
              <strong>{{ task.model }}</strong>
              <div class="small-muted">{{ task.status }} · {{ task.current_status || '–' }}</div>
            </div>
            <Tag :severity="tagSeverity(task.status)" :value="`${task.progress || 0}%`" />
          </div>
          <ProgressBar :value="task.progress || 0" />
          <div class="task-log">{{ latestPullLog(task) }}</div>
        </div>
      </div>
    </div>

    <div class="side-panel-card">
      <h3 style="margin-top:0">Query Console</h3>
      <div class="form-grid">
        <div>
          <label class="field-label">Modell</label>
          <Select v-model="query.model" :options="modelOptions" optionLabel="label" optionValue="value" placeholder="Modell wählen" style="width:100%" />
        </div>
        <div>
          <label class="field-label">Temperatur</label>
          <InputNumber v-model="query.temperature" :min="0" :max="2" :step="0.1" :minFractionDigits="1" :maxFractionDigits="1" style="width:100%" />
        </div>
        <div>
          <label class="field-label">Keep-Alive</label>
          <InputText v-model="query.keep_alive" placeholder="z. B. 5m oder 0" style="width:100%" />
        </div>
        <div class="field-checkbox-row">
          <Checkbox v-model="query.stream" binary inputId="stream-mode" />
          <label for="stream-mode">Streaming mit Schrittanzeige</label>
        </div>
      </div>

      <div style="margin-top:1rem;">
        <label class="field-label">System Prompt</label>
        <Textarea v-model="query.system" rows="3" autoResize style="width:100%" placeholder="Optionaler System Prompt" />
      </div>
      <div style="margin-top:1rem;">
        <label class="field-label">Prompt</label>
        <Textarea v-model="query.prompt" rows="8" autoResize style="width:100%" placeholder="Frage oder Testprompt eingeben" />
      </div>

      <div class="toolbar-row">
        <Button label="Ausführen" icon="pi pi-play" @click="runQuery" :loading="runningQuery" />
        <Button label="Verlauf laden" icon="pi pi-history" severity="secondary" @click="loadGenerateTasks" />
      </div>

      <div v-if="currentTask" class="status-panel">
        <div class="toolbar-row toolbar-space-between" style="margin-top:0; margin-bottom:0.5rem;">
          <div>
            <strong>Status: {{ currentTask.status }}</strong>
            <div class="small-muted">{{ currentTask.current_phase || '–' }} · {{ currentTask.current_message || '–' }}</div>
          </div>
          <Tag :severity="tagSeverity(currentTask.status)" :value="`${currentTask.progress || 0}%`" />
        </div>
        <ProgressBar :value="currentTask.progress || 0" />
        <div class="step-list" v-if="currentTask.steps?.length">
          <div v-for="(step, index) in currentTask.steps.slice(-8)" :key="index" class="step-item">
            <span class="step-time">{{ formatTimestamp(step.timestamp) }}</span>
            <span class="step-phase">{{ step.phase }}</span>
            <span>{{ step.message }}</span>
          </div>
        </div>
      </div>

      <div style="margin-top:1rem;">
        <h4 style="margin:0 0 0.5rem">Antwort</h4>
        <pre class="console-output">{{ currentTask?.response || syncResponse || 'Noch keine Antwort.' }}</pre>
      </div>

      <div v-if="currentTask?.metrics || syncMetrics" style="margin-top:1rem;">
        <h4 style="margin:0 0 0.5rem">Metriken</h4>
        <div class="meta-grid">
          <div class="meta-item"><div class="small-muted">Prompt-Tokens</div><strong>{{ (currentTask?.metrics || syncMetrics)?.prompt_eval_count ?? '–' }}</strong></div>
          <div class="meta-item"><div class="small-muted">Output-Tokens</div><strong>{{ (currentTask?.metrics || syncMetrics)?.eval_count ?? '–' }}</strong></div>
          <div class="meta-item"><div class="small-muted">Load Duration</div><strong>{{ formatDuration((currentTask?.metrics || syncMetrics)?.load_duration) }}</strong></div>
          <div class="meta-item"><div class="small-muted">Total Duration</div><strong>{{ formatDuration((currentTask?.metrics || syncMetrics)?.total_duration) }}</strong></div>
        </div>
      </div>

      <div style="margin-top:1rem;">
        <h4 style="margin:0 0 0.5rem">Letzte Queries</h4>
        <div v-if="generateTasks.length" class="history-list">
          <div v-for="task in generateTasks.slice(0, 6)" :key="task.id" class="meta-item history-item" @click="selectTask(task.id)">
            <div class="toolbar-row toolbar-space-between" style="margin:0;">
              <strong>{{ task.model }}</strong>
              <Tag :severity="tagSeverity(task.status)" :value="task.status" />
            </div>
            <div class="small-muted">{{ formatTimestamp(task.created_at) }}</div>
            <div class="small-muted ellipsis-two">{{ task.prompt }}</div>
          </div>
        </div>
        <div v-else class="small-muted">Noch keine Query-Historie vorhanden.</div>
      </div>
    </div>

    <Dialog v-model:visible="detailsVisible" modal header="Modell-Details" :style="{ width: '70rem' }">
      <div v-if="detailsPayload" class="detail-grid">
        <div class="meta-item">
          <div class="small-muted">Modell</div>
          <strong>{{ detailsPayload.model }}</strong>
        </div>
        <pre class="json-box">{{ prettyJson(detailsPayload.details) }}</pre>
      </div>
    </Dialog>

    <Dialog v-model:visible="copyVisible" modal header="Modell kopieren" :style="{ width: '32rem' }">
      <div class="form-grid">
        <div>
          <label class="field-label">Quelle</label>
          <InputText v-model="copyForm.source" disabled style="width:100%" />
        </div>
        <div>
          <label class="field-label">Neuer Name</label>
          <InputText v-model="copyForm.destination" placeholder="z. B. mein-modell:test" style="width:100%" />
        </div>
      </div>
      <template #footer>
        <Button label="Abbrechen" severity="secondary" @click="copyVisible = false" />
        <Button label="Kopie erstellen" @click="copyModel" :loading="copying" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import ProgressBar from 'primevue/progressbar'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import {
  getAdminOllamaHealth,
  getAdminOllamaModels,
  getAdminOllamaModelDetails,
  deleteAdminOllamaModel,
  copyAdminOllamaModel,
  createAdminGenerateTask,
  getAdminGenerateTask,
  listAdminGenerateTasks,
  runAdminGenerate,
  pullOllamaModel,
  getPullTasks,
} from '@/api'

const loading = ref(false)
const installing = ref(false)
const modelsPayload = ref({ models: [], curated_models: [], default_model: null })
const health = ref({ reachable: false })
const selectedCuratedModel = ref(null)
const customModelName = ref('')
const pullTasks = ref([])
const detailsVisible = ref(false)
const detailsPayload = ref(null)
const copyVisible = ref(false)
const copyForm = ref({ source: '', destination: '' })
const copying = ref(false)
const runningQuery = ref(false)
const syncResponse = ref('')
const syncMetrics = ref(null)
const generateTasks = ref([])
const currentTaskId = ref(null)
const currentTask = ref(null)
let pollTimer = null

const query = ref({
  model: '',
  prompt: 'Gib mir drei kurze Testsätze zum aktuellen Modell aus.',
  system: '',
  temperature: 0.2,
  keep_alive: '5m',
  stream: true,
})

const models = computed(() => modelsPayload.value.models || [])
const modelOptions = computed(() => models.value.map((item) => ({ label: item.name, value: item.name })))
const curatedModelOptions = computed(() => (modelsPayload.value.curated_models || []).map((name) => ({ label: name, value: name })))
const activePullTasks = computed(() => (pullTasks.value || []).filter((task) => ['queued', 'running'].includes(task.status)))

function latestPullLog(task) {
  const log = task?.log || []
  return log[log.length - 1] || task?.current_status || 'Warte auf Updates …'
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

function formatDuration(value) {
  if (!value && value !== 0) return '–'
  return `${Math.round((value || 0) / 1_000_000)} ms`
}

function formatTimestamp(value) {
  if (!value) return '–'
  try {
    return new Date(value).toLocaleString('de-DE')
  } catch {
    return value
  }
}

function tagSeverity(status) {
  if (['completed', 'ok', 'online'].includes(status)) return 'success'
  if (['failed', 'error', 'offline'].includes(status)) return 'danger'
  if (['running', 'queued'].includes(status)) return 'warn'
  return 'secondary'
}

function prettyJson(value) {
  return JSON.stringify(value, null, 2)
}

async function loadAll() {
  loading.value = true
  try {
    const [healthPayload, modelsResult, tasksPayload, generatePayload] = await Promise.all([
      getAdminOllamaHealth(),
      getAdminOllamaModels(),
      getPullTasks(),
      listAdminGenerateTasks(),
    ])
    health.value = healthPayload
    modelsPayload.value = modelsResult
    pullTasks.value = tasksPayload.tasks || []
    generateTasks.value = generatePayload.tasks || []
    if (!query.value.model) {
      query.value.model = modelsResult.default_model || modelsResult.models?.[0]?.name || ''
    }
  } finally {
    loading.value = false
  }
}

async function loadGenerateTasks() {
  const generatePayload = await listAdminGenerateTasks()
  generateTasks.value = generatePayload.tasks || []
}

async function installModel() {
  const name = (customModelName.value || selectedCuratedModel.value || '').trim()
  if (!name) return
  installing.value = true
  try {
    await pullOllamaModel(name)
    customModelName.value = ''
    await loadAll()
  } finally {
    installing.value = false
  }
}

async function openDetails(modelName) {
  detailsPayload.value = await getAdminOllamaModelDetails(modelName)
  detailsVisible.value = true
}

function openCopy(modelName) {
  copyForm.value = { source: modelName, destination: `${modelName}-copy` }
  copyVisible.value = true
}

async function copyModel() {
  if (!copyForm.value.source || !copyForm.value.destination) return
  copying.value = true
  try {
    await copyAdminOllamaModel(copyForm.value.source, copyForm.value.destination)
    copyVisible.value = false
    await loadAll()
  } finally {
    copying.value = false
  }
}

async function removeModel(modelName) {
  if (!window.confirm(`Modell ${modelName} wirklich löschen?`)) return
  await deleteAdminOllamaModel(modelName)
  await loadAll()
}

async function runQuery() {
  if (!query.value.model || !query.value.prompt.trim()) return
  runningQuery.value = true
  syncResponse.value = ''
  syncMetrics.value = null
  currentTask.value = null
  try {
    if (query.value.stream) {
      const payload = await createAdminGenerateTask({ ...query.value })
      currentTaskId.value = payload.task_id
      await pollCurrentTask()
      await loadGenerateTasks()
    } else {
      const data = await runAdminGenerate({ ...query.value, stream: false })
      syncResponse.value = data.response || ''
      syncMetrics.value = {
        total_duration: data.total_duration,
        load_duration: data.load_duration,
        prompt_eval_count: data.prompt_eval_count,
        eval_count: data.eval_count,
      }
    }
  } finally {
    runningQuery.value = false
  }
}

async function pollCurrentTask() {
  if (!currentTaskId.value) return
  const payload = await getAdminGenerateTask(currentTaskId.value)
  currentTask.value = payload
}

async function selectTask(taskId) {
  currentTaskId.value = taskId
  await pollCurrentTask()
}

function startPolling() {
  stopPolling()
  pollTimer = window.setInterval(async () => {
    await loadGenerateTasks()
    const tasksPayload = await getPullTasks()
    pullTasks.value = tasksPayload.tasks || []
    if (currentTaskId.value) {
      await pollCurrentTask()
    }
  }, 2000)
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
