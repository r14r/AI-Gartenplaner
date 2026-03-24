const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function jsonRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!response.ok) {
    let detail = ''
    try {
      const payload = await response.json()
      detail = payload.detail || JSON.stringify(payload)
    } catch {
      detail = response.statusText
    }
    throw new Error(detail || `Request failed (${response.status})`)
  }
  return response.json()
}

export async function analyzeBed(payload) {
  return jsonRequest('/api/ai/analyze-bed', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export async function autoPlan(payload) {
  return jsonRequest('/api/ai/auto-plan', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export async function backendHealth() {
  return jsonRequest('/api/health')
}

export async function getConfig() {
  return jsonRequest('/api/config')
}

export async function updateConfig(payload) {
  return jsonRequest('/api/config', {
    method: 'PUT',
    body: JSON.stringify(payload)
  })
}

export async function getOllamaModels() {
  return jsonRequest('/api/ollama/models')
}

export async function getOllamaCache() {
  return jsonRequest('/api/ollama/cache')
}

export async function getPullTasks() {
  return jsonRequest('/api/ollama/pull-tasks')
}

export async function getPullTask(taskId) {
  return jsonRequest(`/api/ollama/pull-tasks/${taskId}`)
}

export async function pullOllamaModel(model) {
  return jsonRequest('/api/ollama/pull', {
    method: 'POST',
    body: JSON.stringify({ model })
  })
}

export async function createAnalyzeBedTask(payload) {
  return jsonRequest('/api/ai/analyze-bed-task', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export async function getAnalyzeBedTask(taskId) {
  return jsonRequest(`/api/ai/analyze-bed-task/${taskId}`)
}


export async function getAdminOllamaHealth() {
  return jsonRequest('/api/admin/ollama/health')
}

export async function getAdminOllamaModels() {
  return jsonRequest('/api/admin/ollama/models')
}

export async function getAdminOllamaModelDetails(modelName) {
  return jsonRequest(`/api/admin/ollama/models/${encodeURIComponent(modelName)}`)
}

export async function deleteAdminOllamaModel(modelName) {
  return jsonRequest(`/api/admin/ollama/models/${encodeURIComponent(modelName)}`, {
    method: 'DELETE'
  })
}

export async function copyAdminOllamaModel(source, destination) {
  return jsonRequest('/api/admin/ollama/copy', {
    method: 'POST',
    body: JSON.stringify({ source, destination })
  })
}

export async function createAdminGenerateTask(payload) {
  return jsonRequest('/api/admin/ollama/generate-task', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export async function getAdminGenerateTask(taskId) {
  return jsonRequest(`/api/admin/ollama/generate-task/${taskId}`)
}

export async function listAdminGenerateTasks() {
  return jsonRequest('/api/admin/ollama/generate-tasks')
}

export async function runAdminGenerate(payload) {
  return jsonRequest('/api/admin/ollama/generate', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}
