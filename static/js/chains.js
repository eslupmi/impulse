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
        
        expandedEvents.push({
            ...chain,
            isOriginal: true
        });
        
        let currentStart = new Date(startDate.getTime() + intervalDays * msPerDay);
        const maxOccurrences = 52;
        let count = 0;
        
        while (currentStart <= rangeEnd && count < maxOccurrences) {
            if (currentStart >= rangeStart) {
                const occurrence = {
                    ...chain,
                    id: `${chain.id}_${currentStart.toISOString()}`,
                    originalId: chain.id,
                    start: currentStart.toISOString(),
                    end: endDate ? new Date(currentStart.getTime() + duration).toISOString() : null,
                    isOccurrence: true
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

function getExpandedChains(chains) {
    const now = new Date();
    const rangeStart = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const rangeEnd = new Date(now.getFullYear(), now.getMonth() + 3, 0);
    return expandRecurringEvents(chains, rangeStart, rangeEnd);
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
        const index = chains.findIndex(c => c.id === currentChainId);
        if (index !== -1) {
            chains[index] = {
                ...chains[index],
                start,
                end: end || null,
                repeat: repeat || null,
                steps: steps.length > 0 ? steps : null
            };
        }
    } else {
        chains.push({
            id: generateId(),
            title: '',
            start,
            end: end || null,
            repeat: repeat || null,
            steps: steps.length > 0 ? steps : null
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
            events: expandedChains,

            select: function(info) {
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
                        steps: originalChain.steps
                    });
                } else {
                    openChainEditModal({
                        id: info.event.id,
                        start: info.event.start,
                        end: info.event.end,
                        repeat: info.event.extendedProps?.repeat,
                        steps: info.event.extendedProps?.steps
                    });
                }
            },

            eventDrop: async function(info) {
                if (info.event.extendedProps?.isOccurrence) {
                    info.revert();
                    return;
                }
                const chains = await loadChains();
                const index = chains.findIndex(c => c.id === info.event.id);
                if (index !== -1) {
                    chains[index].start = info.event.start.toISOString();
                    chains[index].end = info.event.end ? info.event.end.toISOString() : null;
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
                const chains = await loadChains();
                const index = chains.findIndex(c => c.id === info.event.id);
                if (index !== -1) {
                    chains[index].start = info.event.start.toISOString();
                    chains[index].end = info.event.end ? info.event.end.toISOString() : null;
                    await saveChains(chains);
                    const expandedChains = getExpandedChains(chains);
                    calendar.removeAllEvents();
                    calendar.addEventSource(expandedChains);
                    monthCalendar.removeAllEvents();
                    monthCalendar.addEventSource(expandedChains);
                }
            },

            datesSet: function() {
                if (monthCalendar) {
                    monthCalendar.gotoDate(calendar.view.currentStart);
                    monthCalendar.render();
                }
                setTimeout(() => {
                    const axisCushions = document.querySelectorAll('#calendar .fc-timegrid-axis-cushion');
                    axisCushions.forEach(el => {
                        if (el.textContent) {
                            el.textContent = el.textContent.replace(/W\s+(\d+)/g, 'W$1');
                        }
                    });
                }, 50);
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
            }
            }
        });

        calendar.render();
        monthCalendar.render();
        
        setTimeout(() => {
            const axisCushions = document.querySelectorAll('#calendar .fc-timegrid-axis-cushion');
            axisCushions.forEach(el => {
                if (el.textContent) {
                    el.textContent = el.textContent.replace(/W\s+(\d+)/g, 'W$1');
                }
            });
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
