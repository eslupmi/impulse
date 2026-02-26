let calendar = null;
let monthCalendar = null;
let currentChainId = null;
let chainsConfig = { users: [], user_groups: [], groups: [], chains: [], webhooks: [], week_start: "Mon" };
let initialized = false;
let cachedChains = [];

function getHttpPrefix() {
    const pathParts = window.location.pathname.split('/').filter(p => p);
    return pathParts.length > 1 ? '/' + pathParts[0] : '';
}

function expandRecurringEvents(chains, rangeStart, rangeEnd) {
    const expandedEvents = [];
    const msPerDay = 24 * 60 * 60 * 1000;
    
    chains.forEach(chain => {
        if (!chain.repeat) {
            expandedEvents.push(chain);
            return;
        }
        
        const startDate = new Date(chain.start);
        const endDate = chain.end ? new Date(chain.end) : null;
        const duration = endDate ? endDate.getTime() - startDate.getTime() : msPerDay;
        const repeatEndDate = chain.repeatEnd ? new Date(chain.repeatEnd) : null;
        const originalBgColor = chain.backgroundColor;
        const originalBorderColor = chain.borderColor;
        
        let intervalDays;
        switch (chain.repeat) {
            case 'daily': intervalDays = 1; break;
            case 'weekly': intervalDays = 7; break;
            case 'monthly': intervalDays = 30; break;
            case 'yearly': intervalDays = 365; break;
            default: 
                expandedEvents.push(chain);
                return;
        }
        
        if (!repeatEndDate || (endDate ? endDate <= repeatEndDate : startDate <= repeatEndDate)) {
            expandedEvents.push({
                ...chain,
                isOriginal: true
            });
        }
        
        let currentStart = new Date(startDate.getTime() + intervalDays * msPerDay);
        const maxOccurrences = 52;
        let count = 0;
        const effectiveRangeEnd = repeatEndDate && repeatEndDate < rangeEnd ? repeatEndDate : rangeEnd;
        
        while (currentStart <= effectiveRangeEnd && count < maxOccurrences) {
            const currentEnd = endDate ? new Date(currentStart.getTime() + duration) : new Date(currentStart.getTime() + msPerDay);
            
            if (repeatEndDate && currentEnd > repeatEndDate) {
                break;
            }
            
            if (currentStart >= rangeStart) {
                const occurrence = {
                    ...chain,
                    id: `${chain.id}_${currentStart.toISOString()}`,
                    originalId: chain.id,
                    start: currentStart.toISOString(),
                    end: endDate ? new Date(currentStart.getTime() + duration).toISOString() : null,
                    isOccurrence: true,
                    backgroundColor: originalBgColor,
                    borderColor: originalBorderColor
                };
                expandedEvents.push(occurrence);
            }
            
            if (chain.repeat === 'monthly') {
                currentStart = new Date(startDate);
                currentStart.setMonth(currentStart.getMonth() + Math.floor((currentStart.getTime() - startDate.getTime()) / (30 * msPerDay)) + 1);
            } else if (chain.repeat === 'yearly') {
                currentStart = new Date(startDate);
                currentStart.setFullYear(currentStart.getFullYear() + Math.floor((currentStart.getTime() - startDate.getTime()) / (365 * msPerDay)) + 1);
            } else {
                currentStart = new Date(currentStart.getTime() + intervalDays * msPerDay);
            }
            count++;
        }
    });
    
    return expandedEvents;
}

function prepareEventsForCalendar(chains) {
    const now = new Date();
    const rangeStart = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const rangeEnd = new Date(now.getFullYear(), now.getMonth() + 3, 0);
    const expanded = expandRecurringEvents(chains, rangeStart, rangeEnd);
    
    return expanded.map((chain, index) => {
        const stepsText = formatStepsText(chain.steps);
        const priority = chain.priority !== undefined ? chain.priority : 2;
        
        return {
            ...chain,
            title: stepsText || chain.title || '',
            extendedProps: {
                ...chain.extendedProps,
                steps: chain.steps,
                repeat: chain.repeat,
                repeatEnd: chain.repeatEnd,
                priority: priority,
                originalId: chain.originalId,
                isOccurrence: chain.isOccurrence,
                isOriginal: chain.isOriginal
            },
            display: 'block',
            backgroundColor: chain.backgroundColor || '#3b82f6',
            borderColor: chain.borderColor || '#2563eb'
        };
    }).sort((a, b) => {
        const timeDiff = new Date(a.start) - new Date(b.start);
        if (Math.abs(timeDiff) < 1000) {
            const priority1 = a.extendedProps?.priority !== undefined ? a.extendedProps.priority : 2;
            const priority2 = b.extendedProps?.priority !== undefined ? b.extendedProps.priority : 2;
            return priority1 - priority2;
        }
        return timeDiff;
    });
}

function getExpandedChains(chains) {
    return prepareEventsForCalendar(chains);
}

async function loadChains() {
    try {
        const response = await fetch(`${getHttpPrefix()}/managed_chains`);
        if (response.ok) {
            cachedChains = await response.json();
            return cachedChains;
        }
    } catch (error) {
        console.error('Failed to load managed chains:', error);
    }
    return cachedChains;
}

async function saveChains(chains) {
    cachedChains = chains;
    try {
        const response = await fetch(`${getHttpPrefix()}/managed_chains`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(chains)
        });
        if (!response.ok) {
            console.error('Failed to save managed chains');
        }
    } catch (error) {
        console.error('Failed to save managed chains:', error);
    }
}

function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

async function loadChainsConfig() {
    try {
        const response = await fetch(`${getHttpPrefix()}/chains_config`);
        if (response.ok) {
            chainsConfig = await response.json();
        } else {
            console.error('Failed to load chains config, status:', response.status);
        }
    } catch (error) {
        console.error('Failed to load chains config:', error);
    }
}

function getStepTypeOptions(stepType) {
    switch (stepType) {
        case 'user':
            return chainsConfig.users;
        case 'user_group':
            return chainsConfig.user_groups;
        case 'group':
            return chainsConfig.groups;
        case 'chain':
            return chainsConfig.chains;
        case 'wait':
            return [];
        default:
            return [];
    }
}

function createStepElement(step = null, index = null) {
    const stepDiv = document.createElement('div');
    stepDiv.className = 'step-item';
    
    const stepType = step ? Object.keys(step)[0] : 'user';
    const stepValue = step ? step[stepType] : '';
    
    stepDiv.innerHTML = `
        <div class="step-controls">
            <select class="step-type">
                <option value="user" ${stepType === 'user' ? 'selected' : ''}>user</option>
                <option value="user_group" ${stepType === 'user_group' ? 'selected' : ''}>user_group</option>
                <option value="group" ${stepType === 'group' ? 'selected' : ''}>group</option>
                <option value="wait" ${stepType === 'wait' ? 'selected' : ''}>wait</option>
                <option value="chain" ${stepType === 'chain' ? 'selected' : ''}>chain</option>
            </select>
            <input type="text" class="step-value" placeholder="Enter value" value="${stepValue}" list="step-options-${index || Date.now()}">
            <datalist id="step-options-${index || Date.now()}"></datalist>
            <button type="button" class="btn-remove-step">Remove</button>
        </div>
    `;
    
    const typeSelect = stepDiv.querySelector('.step-type');
    const valueInput = stepDiv.querySelector('.step-value');
    const datalist = stepDiv.querySelector('datalist');
    const removeBtn = stepDiv.querySelector('.btn-remove-step');
    
    function updateOptions() {
        const options = getStepTypeOptions(typeSelect.value);
        datalist.innerHTML = '';
        options.forEach(option => {
            const optionEl = document.createElement('option');
            optionEl.value = option;
            datalist.appendChild(optionEl);
        });
        
        if (typeSelect.value === 'wait') {
            valueInput.placeholder = '5m';
        } else {
            valueInput.placeholder = 'Enter value';
        }
    }
    
    typeSelect.addEventListener('change', updateOptions);
    updateOptions();
    
    removeBtn.addEventListener('click', () => {
        stepDiv.remove();
    });
    
    return stepDiv;
}

function renderSteps(steps = []) {
    const stepsContainer = document.getElementById('steps-container');
    stepsContainer.innerHTML = '';
    if (steps.length === 0) {
        stepsContainer.appendChild(createStepElement());
    } else {
        steps.forEach((step, index) => {
            stepsContainer.appendChild(createStepElement(step, index));
        });
    }
}

function getSteps() {
    const stepsContainer = document.getElementById('steps-container');
    const stepItems = stepsContainer.querySelectorAll('.step-item');
    const steps = [];
    stepItems.forEach(item => {
        const type = item.querySelector('.step-type').value;
        const value = item.querySelector('.step-value').value.trim();
        if (value) {
            steps.push({ [type]: value });
        }
    });
    return steps;
}

function formatStepsText(steps) {
    if (!steps || !Array.isArray(steps) || steps.length === 0) {
        return '';
    }
    
    const stepTexts = steps.map(step => {
        const type = Object.keys(step)[0];
        const value = step[type];
        switch (type) {
            case 'user':
                return `user: ${value}`;
            case 'user_group':
                return `user_group: ${value}`;
            case 'group':
                return `group: ${value}`;
            case 'wait':
                return `wait: ${value}`;
            case 'chain':
                return `chain: ${value}`;
            default:
                return `${type}: ${value}`;
        }
    });
    
    return stepTexts.join('<br>');
}

function findOverlappingChains(chains, start, end, excludeId = null) {
    const startDate = new Date(start);
    const endDate = end ? new Date(end) : new Date(startDate.getTime() + 24 * 60 * 60 * 1000);
    
    return chains.filter(chain => {
        if (excludeId && chain.id === excludeId) return false;
        if (!chain.start) return false;
        
        const chainStart = new Date(chain.start);
        const chainEnd = chain.end ? new Date(chain.end) : new Date(chainStart.getTime() + 24 * 60 * 60 * 1000);
        
        const timeOverlap = startDate < chainEnd && endDate > chainStart;
        const sameDay = startDate.toDateString() === chainStart.toDateString();
        
        return timeOverlap && sameDay;
    });
}

function calculateNewPriority(overlappingChains) {
    if (overlappingChains.length === 0) {
        return 2;
    }
    
    const priorities = overlappingChains
        .map(c => c.priority !== undefined ? c.priority : 2)
        .filter(p => p >= 1 && p <= 2);
    
    if (priorities.length === 0) {
        return 2;
    }
    
    const minPriority = Math.min(...priorities);
    const newPriority = Math.max(1, minPriority - 1);
    
    return newPriority;
}

function findOverlappingEvents(event) {
    const eventStart = event.start;
    const eventEnd = event.end;
    
    const allEvents = calendar.getEvents();
    return allEvents.filter(evt => {
        if (evt.id === event.id || evt.extendedProps?.isOccurrence) {
            return false;
        }
        const evtStart = evt.start;
        const evtEnd = evt.end;
        const timeOverlap = eventStart < evtEnd && eventEnd > evtStart;
        if (!timeOverlap) {
            return false;
        }
        const sameDay = eventStart.toDateString() === evtStart.toDateString();
        return sameDay;
    });
}

function countOverlappingEvents(start, end, excludeEventId = null) {
    if (!calendar) {
        return 0;
    }
    
    const startDate = start instanceof Date ? start : new Date(start);
    const endDate = end ? (end instanceof Date ? end : new Date(end)) : new Date(startDate.getTime() + 24 * 60 * 60 * 1000);
    
    const allEvents = calendar.getEvents();
    return allEvents.filter(evt => {
        if (excludeEventId) {
            const evtOriginalId = evt.extendedProps?.originalId || evt.id;
            if (evtOriginalId === excludeEventId || evt.id === excludeEventId) {
                return false;
            }
        }
        if (evt.extendedProps?.isOccurrence) {
            return false;
        }
        const evtStart = evt.start;
        const evtEnd = evt.end || new Date(evtStart.getTime() + 24 * 60 * 60 * 1000);
        const timeOverlap = startDate < evtEnd && endDate > evtStart;
        if (!timeOverlap) {
            return false;
        }
        const sameDay = startDate.toDateString() === evtStart.toDateString();
        return sameDay;
    }).length;
}

function showOverlapError() {
    const errorMsg = 'Cannot create more than two overlapping events';
    
    const notification = document.createElement('div');
    notification.className = 'overlap-notification';
    notification.textContent = errorMsg;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        notification.classList.remove('show');
        notification.classList.add('hide');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 4000);
}

function showError(message) {
    const notification = document.createElement('div');
    notification.className = 'overlap-notification';
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        notification.classList.remove('show');
        notification.classList.add('hide');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 4000);
}

function findFutureSingleEvents(chains, start, excludeId = null) {
    const startDate = new Date(start);
    
    return chains.filter(chain => {
        if (excludeId && chain.id === excludeId) return false;
        if (!chain.start) return false;
        if (chain.repeat) return false;
        
        const chainStart = new Date(chain.start);
        return chainStart >= startDate;
    });
}

function findFutureRepeatEvents(chains, start, excludeId = null) {
    const startDate = new Date(start);
    
    return chains.filter(chain => {
        if (excludeId && chain.id === excludeId) return false;
        if (!chain.start) return false;
        if (!chain.repeat) return false;
        
        const chainStart = new Date(chain.start);
        return chainStart >= startDate;
    });
}

async function changeEventPriority(event, overlappingEvent) {
    const currentPriority = event.extendedProps?.priority !== undefined ? event.extendedProps.priority : 2;
    const newPriority = currentPriority === 1 ? 2 : 1;
    const otherNewPriority = newPriority === 1 ? 2 : 1;
    
    event.setExtendedProp('priority', newPriority);
    overlappingEvent.setExtendedProp('priority', otherNewPriority);
    
    const chains = await loadChains();
    const originalId1 = event.extendedProps?.originalId || event.id;
    const originalId2 = overlappingEvent.extendedProps?.originalId || overlappingEvent.id;
    
    const index1 = chains.findIndex(c => c.id === originalId1);
    const index2 = chains.findIndex(c => c.id === originalId2);
    
    if (index1 !== -1) {
        chains[index1].priority = newPriority;
    }
    if (index2 !== -1) {
        chains[index2].priority = otherNewPriority;
    }
    
    await saveChains(chains);
    
    const expandedChains = getExpandedChains(chains);
    calendar.removeAllEvents();
    calendar.addEventSource(expandedChains);
    monthCalendar.removeAllEvents();
    monthCalendar.addEventSource(expandedChains);
}

async function updateEventPriority(droppedEvent) {
    const droppedStart = droppedEvent.start;
    const droppedEnd = droppedEvent.end;
    
    const allEvents = calendar.getEvents();
    const overlappingEvents = allEvents.filter(evt => {
        if (evt.id === droppedEvent.id || evt.extendedProps?.isOccurrence) {
            return false;
        }
        const evtStart = evt.start;
        const evtEnd = evt.end;
        const timeOverlap = droppedStart < evtEnd && droppedEnd > evtStart;
        if (!timeOverlap) {
            return false;
        }
        const sameDay = droppedStart.toDateString() === evtStart.toDateString();
        return sameDay;
    });
    
    if (overlappingEvents.length === 0) {
        droppedEvent.setExtendedProp('priority', 2);
        return;
    }
    
    const priorities = overlappingEvents.map(evt => 
        evt.extendedProps?.priority !== undefined ? evt.extendedProps.priority : 2
    );
    
    const minPriority = Math.min(...priorities);
    const newPriority = Math.max(1, minPriority - 1);
    
    droppedEvent.setExtendedProp('priority', newPriority);
}

function formatDateTime(date) {
    const d = new Date(date);
    const pad = (n) => n.toString().padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}, ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function parseDateTime(dateStr) {
    const match = dateStr.match(/(\d{4})-(\d{2})-(\d{2}),\s*(\d{2}):(\d{2})/);
    if (!match) return null;
    const [, year, month, day, hour, minute] = match;
    return new Date(year, month - 1, day, hour, minute).toISOString();
}

function openChainEditModal(chainData = null) {
    const modal = document.getElementById('chain-modal');
    const modalTitle = document.getElementById('modal-title');
    const startInput = document.getElementById('chain-start');
    const endInput = document.getElementById('chain-end');
    const repeatSelect = document.getElementById('chain-repeat');
    const deleteBtn = document.getElementById('delete-chain-btn');

    if (chainData) {
        currentChainId = chainData.id;
        modalTitle.textContent = 'Edit Chain';
        startInput.value = formatDateTime(chainData.start);
        endInput.value = chainData.end ? formatDateTime(chainData.end) : '';
        repeatSelect.value = chainData.repeat || '';
        renderSteps(chainData.steps || []);
        deleteBtn.classList.remove('hidden');
    } else {
        currentChainId = null;
        modalTitle.textContent = 'New Chain';
        startInput.value = '';
        endInput.value = '';
        repeatSelect.value = '';
        renderSteps([]);
        deleteBtn.classList.add('hidden');
    }
    
    modal.classList.add('visible');
}

function closeChainEditModal() {
    const modal = document.getElementById('chain-modal');
    modal.classList.remove('visible');
    currentChainId = null;
}

async function saveChain() {
    const startInput = document.getElementById('chain-start');
    const endInput = document.getElementById('chain-end');
    const repeatSelect = document.getElementById('chain-repeat');

    const startStr = startInput.value.trim();
    const endStr = endInput.value.trim();
    const repeat = repeatSelect.value;
    const steps = getSteps();

    if (!startStr) return;

    const start = parseDateTime(startStr);
    if (!start) return;

    const end = endStr ? parseDateTime(endStr) : null;
    const chains = await loadChains();

    if (currentChainId) {
        const overlapping = findOverlappingChains(chains, start, end, currentChainId);
        if (overlapping.length >= 2) {
            showOverlapError();
            return;
        }
        
        if (repeat) {
            const futureRepeatEvents = findFutureRepeatEvents(chains, start, currentChainId);
            if (futureRepeatEvents.length > 0) {
                showError('Cannot create REPEAT event: another REPEAT event exists in the future');
                return;
            }
            
            const futureSingleEvents = findFutureSingleEvents(chains, start, currentChainId);
            futureSingleEvents.forEach(chain => {
                const index = chains.findIndex(c => c.id === chain.id);
                if (index !== -1 && chains[index].priority !== 1) {
                    chains[index].priority = 1;
                }
            });
        }
        
        const index = chains.findIndex(c => c.id === currentChainId);
        if (index !== -1) {
            const existingChain = chains[index];
            const priority = repeat ? 1 : (existingChain.priority !== undefined ? existingChain.priority : 2);
            
            chains[index] = {
                ...chains[index],
                start,
                end: end || null,
                repeat: repeat || null,
                repeatEnd: existingChain.repeatEnd || null,
                steps: steps.length > 0 ? steps : null,
                priority: priority
            };
        }
        
        await saveChains(chains);
        const expandedChains = getExpandedChains(chains);
        calendar.removeAllEvents();
        calendar.addEventSource(expandedChains);
        monthCalendar.removeAllEvents();
        monthCalendar.addEventSource(expandedChains);
        closeChainEditModal();
        return;
    } else {
        const overlapping = findOverlappingChains(chains, start, end);
        if (overlapping.length >= 2) {
            showOverlapError();
            return;
        }
        
        if (repeat) {
            const futureRepeatEvents = findFutureRepeatEvents(chains, start);
            if (futureRepeatEvents.length > 0) {
                showError('Cannot create REPEAT event: another REPEAT event exists in the future');
                return;
            }
            
            const futureSingleEvents = findFutureSingleEvents(chains, start);
            futureSingleEvents.forEach(chain => {
                const index = chains.findIndex(c => c.id === chain.id);
                if (index !== -1 && chains[index].priority !== 1) {
                    chains[index].priority = 1;
                }
            });
        }
        
        const newPriority = repeat ? 1 : calculateNewPriority(overlapping);
        
        chains.push({
            id: generateId(),
            title: '',
            start,
            end: end || null,
            repeat: repeat || null,
            steps: steps.length > 0 ? steps : null,
            priority: newPriority
        });
    }

    await saveChains(chains);
    const expandedChains = getExpandedChains(chains);
    calendar.removeAllEvents();
    calendar.addEventSource(expandedChains);
    monthCalendar.removeAllEvents();
    monthCalendar.addEventSource(expandedChains);
    closeChainEditModal();
}

async function deleteChain() {
    if (!currentChainId) return;

    const chains = await loadChains();
    const filtered = chains.filter(c => c.id !== currentChainId);
    await saveChains(filtered);
    const expandedChains = getExpandedChains(filtered);
    calendar.removeAllEvents();
    calendar.addEventSource(expandedChains);
    monthCalendar.removeAllEvents();
    monthCalendar.addEventSource(expandedChains);
    closeChainEditModal();
}

function parseWeekStart(weekStart) {
    const weekStartMap = {
        'Mon': 1, '1': 1,
        'Tue': 2, '2': 2,
        'Wed': 3, '3': 3,
        'Thu': 4, '4': 4,
        'Fri': 5, '5': 5,
        'Sat': 6, '6': 6,
        'Sun': 0, '0': 0, '7': 0
    };
    return weekStartMap[weekStart] || 1;
}

function getWeekNumber(date) {
    const d = new Date(date);
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() + 3 - (d.getDay() + 6) % 7);
    const week1 = new Date(d.getFullYear(), 0, 4);
    week1.setHours(0, 0, 0, 0);
    week1.setDate(week1.getDate() + 3 - (week1.getDay() + 6) % 7);
    return 1 + Math.round(((d.getTime() - week1.getTime()) / 86400000) / 7);
}

function updateWeekNumberDisplay() {
    if (!calendar) return;
    
    const weekStart = calendar.view.currentStart;
    const weekNumber = getWeekNumber(weekStart);
    const weekNumberDisplay = document.getElementById('week-number-display');
    
    if (weekNumberDisplay) {
        weekNumberDisplay.textContent = `Week ${weekNumber}`;
    }
}

function updateCurrentWeekHighlight() {
    if (!calendar || !monthCalendar) return;
    
    const weekStart = calendar.view.currentStart;
    const weekEnd = calendar.view.currentEnd;
    
    const dayCells = monthCalendar.el.querySelectorAll('.fc-daygrid-day:not(.fc-day-other)');
    dayCells.forEach(cell => {
        const dateStr = cell.getAttribute('data-date');
        if (!dateStr) return;
        
        const cellDate = new Date(dateStr + 'T00:00:00');
        if (cellDate >= weekStart && cellDate < weekEnd) {
            cell.classList.add('current-week');
        } else {
            cell.classList.remove('current-week');
        }
    });
}

async function initializeCalendars() {
    try {
        console.log('initializeCalendars called, initialized =', initialized);
        
        if (typeof FullCalendar === 'undefined') {
            console.error('FullCalendar is not available!');
            return;
        }
        
        await loadChainsConfig();
        
        const calendarEl = document.getElementById('calendar');
        const monthCalendarEl = document.getElementById('month-calendar');
        
        console.log('Calendar elements:', { calendarEl, monthCalendarEl });
        
        if (!calendarEl || !monthCalendarEl) {
            console.error('Calendar elements not found', { calendarEl, monthCalendarEl });
            return;
        }
        
        if (initialized && calendar && monthCalendar) {
            console.log('Calendars already initialized, re-rendering');
            calendar.render();
            monthCalendar.render();
            
            const prevBtn = document.getElementById('calendar-prev');
            const nextBtn = document.getElementById('calendar-next');
            
            if (prevBtn && !prevBtn.hasAttribute('data-listener-attached')) {
                prevBtn.setAttribute('data-listener-attached', 'true');
                prevBtn.addEventListener('click', () => {
                    calendar.prev();
                    setTimeout(() => updateWeekNumberDisplay(), 50);
                });
            }
            
            if (nextBtn && !nextBtn.hasAttribute('data-listener-attached')) {
                nextBtn.setAttribute('data-listener-attached', 'true');
                nextBtn.addEventListener('click', () => {
                    calendar.next();
                    setTimeout(() => updateWeekNumberDisplay(), 50);
                });
            }
            
            setTimeout(() => {
                calendar.updateSize();
                monthCalendar.updateSize();
            }, 100);
            return;
        }
        
        const firstDay = parseWeekStart(chainsConfig.week_start);

        if (calendar) {
            calendar.destroy();
        }
        if (monthCalendar) {
            monthCalendar.destroy();
        }

        const chains = await loadChains();
        const expandedChains = getExpandedChains(chains);
        
        calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'timeGridWeek',
            headerToolbar: false,
            slotMinHeight: 60,
            allDaySlot: false,
            firstDay: firstDay,
            weekNumbers: true,
            weekNumberCalculation: 'ISO',
            dayHeaderFormat: { weekday: 'short', day: 'numeric', omitCommas: false },
            slotLabelFormat: {
                hour: '2-digit',
                minute: '2-digit',
                hour12: false
            },
            slotDuration: '00:15:00',
            slotLabelInterval: '01:00:00',
            editable: true,
            selectable: true,
            selectMirror: true,
            dayMaxEvents: true,
            eventOrder: function(event1, event2) {
                const time1 = new Date(event1.start).getTime();
                const time2 = new Date(event2.start).getTime();
                if (Math.abs(time1 - time2) < 1000) {
                    const priority1 = event1.extendedProps?.priority !== undefined ? event1.extendedProps.priority : 2;
                    const priority2 = event2.extendedProps?.priority !== undefined ? event2.extendedProps.priority : 2;
                    return priority1 - priority2;
                }
                return time1 - time2;
            },
            eventContent: function(arg) {
                const steps = arg.event.extendedProps?.steps;
                const stepsText = formatStepsText(steps);
                if (stepsText) {
                    return {
                        html: `<div class="fc-event-title" style="line-height: 1.4; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${stepsText}</div>`
                    };
                }
                return { html: '' };
            },
            eventDidMount: function(arg) {
                const el = arg.el;
                const isOccurrence = arg.event.extendedProps?.isOccurrence;
                const hasRepeat = arg.event.extendedProps?.repeat;
                
                const priority = arg.event.extendedProps?.priority !== undefined ? arg.event.extendedProps.priority : 2;
                
                for (let i = 1; i <= 2; i++) {
                    el.classList.remove(`fc-event-priority-${i}`);
                }
                
                el.classList.add(`fc-event-priority-${priority}`);
                el.setAttribute('data-priority', priority.toString());
                el.style.zIndex = 3 - priority;
                
                el.style.setProperty('width', '90%', 'important');
                
                if (isOccurrence && hasRepeat) {
                    setTimeout(() => {
                        if (el.querySelector('.fc-event-repeat-end-btn')) {
                            return;
                        }
                        
                        const repeatEndBtn = document.createElement('button');
                        repeatEndBtn.className = 'fc-event-repeat-end-btn';
                        repeatEndBtn.innerHTML = 'End';
                        repeatEndBtn.title = 'Set repeat end after this event';
                        
                        repeatEndBtn.addEventListener('click', async (e) => {
                            e.stopPropagation();
                            e.preventDefault();
                            const originalId = arg.event.extendedProps?.originalId || arg.event.id;
                            const eventEnd = arg.event.end || new Date(arg.event.start.getTime() + 24 * 60 * 60 * 1000);
                            
                            const chains = await loadChains();
                            const index = chains.findIndex(c => c.id === originalId);
                            
                            if (index !== -1) {
                                chains[index].repeatEnd = eventEnd.toISOString();
                                await saveChains(chains);
                                const expandedChains = getExpandedChains(chains);
                                calendar.removeAllEvents();
                                calendar.addEventSource(expandedChains);
                                monthCalendar.removeAllEvents();
                                monthCalendar.addEventSource(expandedChains);
                            }
                        });
                        
                        repeatEndBtn.style.display = 'none';
                        const eventMain = el.querySelector('.fc-event-main') || el;
                        eventMain.appendChild(repeatEndBtn);
                        
                        el.addEventListener('mouseenter', () => {
                            repeatEndBtn.style.setProperty('display', 'block', 'important');
                        });
                        
                        el.addEventListener('mouseleave', () => {
                            repeatEndBtn.style.setProperty('display', 'none', 'important');
                        });
                    }, 10);
                }
                
                setTimeout(() => {
                    const overlappingEvents = findOverlappingEvents(arg.event);
                    if (overlappingEvents.length > 0) {
                        const overlappingEvent = overlappingEvents[0];
                        const priorityBtn = document.createElement('button');
                        priorityBtn.className = 'fc-event-priority-toggle';
                        priorityBtn.style.display = 'none';
                        priorityBtn.innerHTML = priority === 2 ? '↑' : '↓';
                        priorityBtn.title = priority === 2 ? 'Increase priority' : 'Decrease priority';
                        
                        priorityBtn.addEventListener('click', async (e) => {
                            e.stopPropagation();
                            await changeEventPriority(arg.event, overlappingEvent);
                        });
                        
                        el.appendChild(priorityBtn);
                        
                        el.addEventListener('mouseenter', () => {
                            priorityBtn.style.display = 'block';
                        });
                        
                        el.addEventListener('mouseleave', () => {
                            priorityBtn.style.display = 'none';
                        });
                    }
                }, 50);
            },
            eventTimeFormat: {
                hour: '2-digit',
                minute: '2-digit',
                hour12: false
            },
            displayEventTime: false,
            events: expandedChains,

            select: function(info) {
                const overlapCount = countOverlappingEvents(info.start, info.end);
                if (overlapCount >= 2) {
                    showOverlapError();
                    calendar.unselect();
                    return;
                }
                openChainEditModal();
                document.getElementById('chain-start').value = formatDateTime(info.start);
                if (info.end) {
                    document.getElementById('chain-end').value = formatDateTime(info.end);
                }
                calendar.unselect();
            },

            eventClick: async function(info) {
                const originalId = info.event.extendedProps?.originalId || info.event.id;
                const chains = await loadChains();
                const originalChain = chains.find(c => c.id === originalId);
                
                if (originalChain) {
                    openChainEditModal({
                        id: originalChain.id,
                        start: originalChain.start,
                        end: originalChain.end,
                        repeat: originalChain.repeat,
                        repeatEnd: originalChain.repeatEnd,
                        steps: originalChain.steps
                    });
                } else {
                    openChainEditModal({
                        id: info.event.id,
                        start: info.event.start,
                        end: info.event.end,
                        repeat: info.event.extendedProps?.repeat,
                        repeatEnd: info.event.extendedProps?.repeatEnd,
                        steps: info.event.extendedProps?.steps
                    });
                }
            },

            eventDrop: async function(info) {
                if (info.event.extendedProps?.isOccurrence) {
                    info.revert();
                    return;
                }
                
                const originalId = info.event.extendedProps?.originalId || info.event.id;
                const overlapCount = countOverlappingEvents(info.event.start, info.event.end, originalId);
                if (overlapCount >= 2) {
                    showOverlapError();
                    info.revert();
                    return;
                }
                
                await updateEventPriority(info.event);
                
                const chains = await loadChains();
                const index = chains.findIndex(c => c.id === originalId);
                if (index !== -1) {
                    chains[index].start = info.event.start.toISOString();
                    chains[index].end = info.event.end ? info.event.end.toISOString() : null;
                    chains[index].priority = info.event.extendedProps?.priority !== undefined ? info.event.extendedProps.priority : 2;
                    await saveChains(chains);
                    const expandedChains = getExpandedChains(chains);
                    calendar.removeAllEvents();
                    calendar.addEventSource(expandedChains);
                    monthCalendar.removeAllEvents();
                    monthCalendar.addEventSource(expandedChains);
                }
            },

            eventResize: async function(info) {
                if (info.event.extendedProps?.isOccurrence) {
                    info.revert();
                    return;
                }
                
                const originalId = info.event.extendedProps?.originalId || info.event.id;
                const overlapCount = countOverlappingEvents(info.event.start, info.event.end, originalId);
                if (overlapCount >= 2) {
                    showOverlapError();
                    info.revert();
                    return;
                }
                
                await updateEventPriority(info.event);
                const chains = await loadChains();
                const index = chains.findIndex(c => c.id === originalId);
                if (index !== -1) {
                    chains[index].start = info.event.start.toISOString();
                    chains[index].end = info.event.end ? info.event.end.toISOString() : null;
                    chains[index].priority = info.event.extendedProps?.priority !== undefined ? info.event.extendedProps.priority : 2;
                    await saveChains(chains);
                    const expandedChains = getExpandedChains(chains);
                    calendar.removeAllEvents();
                    calendar.addEventSource(expandedChains);
                    monthCalendar.removeAllEvents();
                    monthCalendar.addEventSource(expandedChains);
                }
            },

            datesSet: function() {
                updateWeekNumberDisplay();
                if (monthCalendar) {
                    monthCalendar.gotoDate(calendar.view.currentStart);
                    monthCalendar.render();
                    setTimeout(() => {
                        updateCurrentWeekHighlight();
                    }, 100);
                }
            }
        });

        monthCalendar = new FullCalendar.Calendar(monthCalendarEl, {
        initialView: 'dayGridMonth',
        headerToolbar: {
            left: 'title',
            center: '',
            right: 'prev,next'
        },
        firstDay: firstDay,
        height: 'auto',
        fixedWeekCount: false,
        showNonCurrentDates: false,
        weekNumbers: true,
        weekNumberCalculation: 'ISO',
        events: expandedChains,

        dateClick: function(info) {
            calendar.gotoDate(info.dateStr);
        },

        dayCellContent: function(info) {
            const dayNum = info.dayNumberText;
            return {
                html: `<div class="day-number">${dayNum}</div>`
            };
        },

        dayCellDidMount: function(info) {
            const cellDate = info.date;
            const weekStart = calendar.view.currentStart;
            const weekEnd = calendar.view.currentEnd;
            
            if (cellDate >= weekStart && cellDate < weekEnd) {
                info.el.classList.add('current-week');
            } else {
                info.el.classList.remove('current-week');
            }
        },

        datesSet: function() {
            setTimeout(() => {
                updateCurrentWeekHighlight();
            }, 50);
        }
        });

        calendar.render();
        monthCalendar.render();
        
        setTimeout(() => {
            updateWeekNumberDisplay();
            updateCurrentWeekHighlight();
        }, 200);
        
        const prevBtn = document.getElementById('calendar-prev');
        const nextBtn = document.getElementById('calendar-next');
        
        if (prevBtn && !prevBtn.hasAttribute('data-listener-attached')) {
            prevBtn.setAttribute('data-listener-attached', 'true');
            prevBtn.addEventListener('click', () => {
                calendar.prev();
                setTimeout(() => updateWeekNumberDisplay(), 50);
            });
        }
        
        if (nextBtn && !nextBtn.hasAttribute('data-listener-attached')) {
            nextBtn.setAttribute('data-listener-attached', 'true');
            nextBtn.addEventListener('click', () => {
                calendar.next();
                setTimeout(() => updateWeekNumberDisplay(), 50);
            });
        }
        
        setTimeout(() => {
            updateWeekNumberDisplay();
        }, 100);
        
        initialized = true;
        console.log('Calendars initialized successfully', { initialized, calendar: !!calendar, monthCalendar: !!monthCalendar });
        
    } catch (error) {
        console.error('Error in initializeCalendars:', error);
        initialized = false;
        throw error;
    }
}

function setupChainEditModalListeners() {
    const modal = document.getElementById('chain-modal');
    const closeBtn = modal.querySelector('.modal-close');
    const saveBtn = document.getElementById('save-chain-btn');
    const deleteBtn = document.getElementById('delete-chain-btn');
    const addStepBtn = document.getElementById('add-step-btn');
    const stepsContainer = document.getElementById('steps-container');

    closeBtn.addEventListener('click', closeChainEditModal);
    saveBtn.addEventListener('click', saveChain);
    deleteBtn.addEventListener('click', deleteChain);
    addStepBtn.addEventListener('click', () => {
        stepsContainer.appendChild(createStepElement());
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeChainEditModal();
        }
    });
}

export const ChainsManager = {
    initialized: false,

    init() {
        if (this.initialized) return;
        
        const chainsModal = document.getElementById('chains-modal');
        const chainsToggle = document.getElementById('chains-toggle');
        const chainsCloseBtn = chainsModal.querySelector('.chains-modal-close');

        chainsToggle.addEventListener('click', async () => {
            chainsModal.classList.add('visible');
            
            if (typeof FullCalendar === 'undefined') {
                console.error('FullCalendar is not loaded!');
                return;
            }
            
            setTimeout(async () => {
                console.log('Initializing calendars...');
                await initializeCalendars();
                console.log('After initializeCalendars, initialized =', initialized);
                
                setTimeout(() => {
                    if (calendar) {
                        calendar.updateSize();
                    }
                    if (monthCalendar) {
                        monthCalendar.updateSize();
                    }
                }, 100);
            }, 200);
        });

        chainsCloseBtn.addEventListener('click', () => {
            chainsModal.classList.remove('visible');
        });

        chainsModal.addEventListener('click', (e) => {
            if (e.target === chainsModal) {
                chainsModal.classList.remove('visible');
            }
        });

        setupChainEditModalListeners();
        this.initialized = true;
    }
};
