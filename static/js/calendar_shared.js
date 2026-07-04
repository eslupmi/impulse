export function attachNavListener(btn, handler) {
    if (btn && !btn.dataset.listenerAttached) {
        btn.dataset.listenerAttached = "true";
        btn.addEventListener("click", handler);
    }
}

export function cleanupFullCalendarDragArtifacts() {
    document.body.classList.remove("fc-not-allowed");
    for (const mirror of document.querySelectorAll(".fc-event-mirror")) {
        mirror.remove();
    }
}

export function destroyFullCalendarInstance(calendarInstance) {
    if (calendarInstance) {
        calendarInstance.destroy();
    }
}

const calendarSuspenders = new Map();

export function registerCalendarSuspender(id, suspend) {
    calendarSuspenders.set(id, suspend);
}

export function suspendOtherCalendars(activeId) {
    for (const [id, suspend] of calendarSuspenders) {
        if (id !== activeId) {
            suspend();
        }
    }
    cleanupFullCalendarDragArtifacts();
}

export function getSharedCalendarOptions(firstDay, timezone) {
    return {
        firstDay,
        timeZone: timezone,
        weekNumbers: true,
        fixedMirrorParent: document.body,
    };
}

export function updateMonthCalendarWeekHighlight(calendar, monthCalendar) {
    if (!calendar || !monthCalendar) return;

    const weekStart = new Date(calendar.view.activeStart);
    weekStart.setHours(0, 0, 0, 0);
    const weekEnd = new Date(calendar.view.activeEnd);
    weekEnd.setHours(0, 0, 0, 0);

    monthCalendar.el.querySelectorAll(".fc-daygrid-day:not(.fc-day-other)").forEach((cell) => {
        const dateStr = cell.dataset.date;
        if (!dateStr) return;

        const cellDate = new Date(`${dateStr}T00:00:00`);
        cellDate.setHours(0, 0, 0, 0);
        cell.classList.toggle("current-week", cellDate >= weekStart && cellDate < weekEnd);
    });
}
