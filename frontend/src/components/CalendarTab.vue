<template>
  <div class="grid-2">
    <div>
      <FullCalendar :options="calendarOptions" />
    </div>
    <div class="side-panel-card">
      <h3 style="margin-top:0">Kalenderdetails</h3>
      <div v-if="selectedEvent">
        <p><strong>Eintrag:</strong> {{ selectedEvent.title }}</p>
        <p><strong>Phase:</strong> {{ selectedEvent.extendedProps.phase }}</p>
        <p><strong>Start:</strong> {{ selectedEvent.startStr }}</p>
        <p><strong>Ende:</strong> {{ selectedEvent.endStr }}</p>
      </div>
      <p v-else class="small-muted">Klicke im Kalender auf einen Eintrag.</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import listPlugin from '@fullcalendar/list'
import interactionPlugin from '@fullcalendar/interaction'
import { seeds } from '@/data/seeds'
import { buildCalendarEvents } from '@/utils/format'

const selectedEvent = ref(null)

const calendarOptions = {
  plugins: [dayGridPlugin, timeGridPlugin, listPlugin, interactionPlugin],
  initialView: 'dayGridMonth',
  locale: 'de',
  height: 'auto',
  headerToolbar: {
    left: 'prev,next today',
    center: 'title',
    right: 'dayGridMonth,timeGridWeek,timeGridDay,listMonth'
  },
  buttonText: {
    today: 'Heute',
    month: 'Monat',
    week: 'Woche',
    day: 'Tag',
    list: 'Liste'
  },
  events: buildCalendarEvents(seeds),
  eventClick(info) {
    selectedEvent.value = info.event
  }
}
</script>
