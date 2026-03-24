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
            <PanelMenu :model="sidebarItems" :expandedKeys="expandedKeys" @update:expandedKeys="expandedKeys = $event" class="app-panel-menu" />
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
            <OllamaAdminTab v-else />
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
const expandedKeys = ref({ planung: true, ki: true })

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
  },
  admin: {
    label: 'Ollama Admin',
    description: 'Installierte Modelle verwalten und Admin-Abfragen ausführen.'
  }
}

const activeViewLabel = computed(() => viewMeta[activeView.value]?.label || 'Ansicht')
const activeViewDescription = computed(() => viewMeta[activeView.value]?.description || '')

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
        command: () => selectView('admin')
      }
    ]
  }
])

function selectView(view) {
  activeView.value = view
}

function updateBeds(newBeds) {
  beds.value = JSON.parse(JSON.stringify(newBeds))
}

function openAiForBed(bedId) {
  selectedAiBedId.value = bedId
  activeView.value = 'ai'
}
</script>
