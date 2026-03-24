<template>
  <div class="app-shell">
    <div class="page-header">
      <h1>Garden AI Planner</h1>
      <p>Samenverwaltung, Aussaatkalender, Beetplanung und KI-gestützte Mischkulturberatung mit Ollama.</p>
    </div>

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

    <Tabs value="seeds">
      <TabList>
        <Tab value="seeds">Samenpäckchen</Tab>
        <Tab value="calendar">Aussaatkalender</Tab>
        <Tab value="beds">Beetplanung</Tab>
        <Tab value="ai">KI-Beetberater</Tab>
        <Tab value="config">Konfiguration</Tab>
        <Tab value="admin">Ollama Admin</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="seeds">
          <SeedListTab />
        </TabPanel>
        <TabPanel value="calendar">
          <CalendarTab />
        </TabPanel>
        <TabPanel value="beds">
          <BedPlannerTab :beds="beds" @update:beds="updateBeds" @analyze-bed="openAiForBed" />
        </TabPanel>
        <TabPanel value="ai">
          <AiAdvisorTab :beds="beds" :initialBedId="selectedAiBedId" />
        </TabPanel>
        <TabPanel value="config">
          <ConfigTab />
        </TabPanel>
        <TabPanel value="admin">
          <OllamaAdminTab />
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
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

function updateBeds(newBeds) {
  beds.value = JSON.parse(JSON.stringify(newBeds))
}

function openAiForBed(bedId) {
  selectedAiBedId.value = bedId
}
</script>
