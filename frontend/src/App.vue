<template>
  <div class="app-shell">
    <header class="page-header">
      <h1>Garden AI Planner</h1>
      <p>Samenverwaltung, Aussaatkalender, Beetplanung und KI-gestützte Mischkulturberatung mit Ollama.</p>
    </header>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Samen im Bestand</div>
        <div class="kpi-value">{{ seeds.length }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Aktive Beete</div>
        <div class="kpi-value">{{ beds.length }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Pflanzungen in Beeten</div>
        <div class="kpi-value">{{ totalAssignedSeeds }}</div>
      </div>
    </div>

    <div class="layout-grid">
      <aside class="sidebar-area">
        <Card>
          <template #title>Navigation</template>
          <template #content>
            <PanelMenu
              :model="sidebarItems"
              :expandedKeys="expandedKeys"
              @update:expandedKeys="expandedKeys = $event"
              class="app-panel-menu"
            />
          </template>
        </Card>
      </aside>

      <main class="content-area">
        <Card>
          <template #title>{{ activeViewLabel }}</template>
          <template #subtitle>{{ activeViewDescription }}</template>
          <template #content>
            <SeedListTab v-if="activeView === 'seeds'" />
            <CalendarTab v-else-if="activeView === 'calendar'" />
            <BedPlannerTab
              v-else-if="activeView === 'beds'"
              :beds="beds"
              @update:beds="updateBeds"
              @analyze-bed="openAiForBed"
            />
            <AiAdvisorTab v-else-if="activeView === 'ai'" :beds="beds" :initialBedId="selectedAiBedId" />
            <ConfigTab v-else-if="activeView === 'config'" />
            <OllamaAdminTab v-else :mode="activeSubView" />
          </template>
        </Card>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import Card from 'primevue/card'
import PanelMenu from 'primevue/panelmenu'
import SeedListTab from '@/components/SeedListTab.vue'
import CalendarTab from '@/components/CalendarTab.vue'
import BedPlannerTab from '@/components/BedPlannerTab.vue'
import AiAdvisorTab from '@/components/AiAdvisorTab.vue'
import ConfigTab from '@/components/ConfigTab.vue'
import OllamaAdminTab from '@/components/OllamaAdminTab.vue'
import { seeds } from '@/data/seeds'
import { defaultBeds } from '@/data/defaultBeds'

const beds = ref(JSON.parse(JSON.stringify(defaultBeds)))
const selectedAiBedId = ref(defaultBeds[0]?.id || null)
const totalAssignedSeeds = computed(() => beds.value.reduce((sum, bed) => sum + bed.seedIds.length, 0))

const activeView = ref('seeds')
const activeSubView = ref('inventory')
const expandedKeys = ref({ planung: true, ki: true, admin: true })

const viewMeta = {
  seeds: {
    label: 'Samenpäckchen',
    description: 'Bestand ansehen und Saatgutdaten verwalten.'
  },
  calendar: {
    label: 'Aussaatkalender',
    description: 'Aussaat-, Pflanz- und Erntezeitpunkte in der Kalenderansicht.'
  },
  beds: {
    label: 'Beetplanung',
    description: 'Beete planen, Bepflanzung zuweisen und Mischkultur prüfen.'
  },
  ai: {
    label: 'KI-Beetberater',
    description: 'Beete per Ollama analysieren und Verbesserungsvorschläge erhalten.'
  },
  config: {
    label: 'Konfiguration',
    description: 'Modelle, Temperatur und App-Einstellungen verwalten.'
  }
}

const adminSubViews = {
  inventory: {
    label: 'Ollama Admin · Modellbestand',
    description: 'Installierte Modelle laden, hinzufügen, kopieren oder löschen.'
  },
  pulls: {
    label: 'Ollama Admin · Installationsstatus',
    description: 'Aktive Pull-Tasks und Fortschritte der Modell-Installationen überwachen.'
  },
  console: {
    label: 'Ollama Admin · Query Console',
    description: 'Manuelle Prompts gegen ein Modell ausführen und Antworten prüfen.'
  },
  history: {
    label: 'Ollama Admin · Query-Historie',
    description: 'Vergangene Admin-Queries öffnen und Statusinformationen einsehen.'
  }
}

const activeViewLabel = computed(() => {
  if (activeView.value === 'admin') {
    return adminSubViews[activeSubView.value]?.label || 'Ollama Admin'
  }
  return viewMeta[activeView.value]?.label || 'Ansicht'
})

const activeViewDescription = computed(() => {
  if (activeView.value === 'admin') {
    return adminSubViews[activeSubView.value]?.description || ''
  }
  return viewMeta[activeView.value]?.description || ''
})

const sidebarItems = computed(() => [
  {
    key: 'planung',
    label: 'Planung',
    icon: 'pi pi-calendar',
    items: [
      {
        key: 'seeds',
        label: 'Samenpäckchen',
        icon: 'pi pi-box',
        command: () => selectView('seeds')
      },
      {
        key: 'calendar',
        label: 'Aussaatkalender',
        icon: 'pi pi-calendar-plus',
        command: () => selectView('calendar')
      },
      {
        key: 'beds',
        label: 'Beetplanung',
        icon: 'pi pi-th-large',
        command: () => selectView('beds')
      }
    ]
  },
  {
    key: 'ki',
    label: 'KI & System',
    icon: 'pi pi-microchip-ai',
    items: [
      {
        key: 'ai',
        label: 'KI-Beetberater',
        icon: 'pi pi-sparkles',
        command: () => selectView('ai')
      },
      {
        key: 'config',
        label: 'Konfiguration',
        icon: 'pi pi-sliders-h',
        command: () => selectView('config')
      },
      {
        key: 'admin',
        label: 'Ollama Admin',
        icon: 'pi pi-cog',
        items: [
          {
            key: 'admin-inventory',
            label: 'Modellbestand',
            icon: 'pi pi-database',
            command: () => selectAdminSubView('inventory')
          },
          {
            key: 'admin-pulls',
            label: 'Installationsstatus',
            icon: 'pi pi-cloud-download',
            command: () => selectAdminSubView('pulls')
          },
          {
            key: 'admin-console',
            label: 'Query Console',
            icon: 'pi pi-play-circle',
            command: () => selectAdminSubView('console')
          },
          {
            key: 'admin-history',
            label: 'Query-Historie',
            icon: 'pi pi-history',
            command: () => selectAdminSubView('history')
          }
        ]
      }
    ]
  }
])

function selectView(view) {
  activeView.value = view
}

function selectAdminSubView(subView) {
  activeView.value = 'admin'
  activeSubView.value = subView
}

function updateBeds(newBeds) {
  beds.value = JSON.parse(JSON.stringify(newBeds))
}

function openAiForBed(bedId) {
  selectedAiBedId.value = bedId
  activeView.value = 'ai'
}
</script>
