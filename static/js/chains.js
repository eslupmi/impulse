import {getSocket} from "./websocket.js";

let calendar = null;
let monthCalendar = null;
let currentChainId = null;
let chainsConfig = { users: [], user_groups: [], groups: [], chains: [], webhooks: [], week_start: "Mon", timezone: "UTC" };
let initialized = false;
let cachedChains = [];
let chainsPromiseResolve = null;
let savePromiseResolve = null;

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
            const originalEvent = {
                ...chain,
                isOriginal: true
            };
            if (repeatEndDate) {
                const originalEnd = endDate ? endDate : new Date(startDate.getTime() + msPerDay);
                if (Math.abs(originalEnd.getTime() - repeatEndDate.getTime()) < msPerDay) {
                    originalEvent.isLastOccurrence = true;
                }
            }
            expandedEvents.push(originalEvent);
        }
        
        let currentStart = new Date(startDate.getTime() + intervalDays * msPerDay);
        const maxOccurrences = 52;
        let count = 0;
        const effectiveRangeEnd = repeatEndDate && repeatEndDate < rangeEnd ? repeatEndDate : rangeEnd;
        let lastOccurrence = null;
        
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
                lastOccurrence = occurrence;
                expandedEvents.push(occurrence);
            }
            
            let nextStart;
            if (chain.repeat === 'monthly') {
                nextStart = new Date(startDate);
                nextStart.setMonth(nextStart.getMonth() + Math.floor((currentStart.getTime() - startDate.getTime()) / (30 * msPerDay)) + 1);
            } else if (chain.repeat === 'yearly') {
                nextStart = new Date(startDate);
                nextStart.setFullYear(nextStart.getFullYear() + Math.floor((currentStart.getTime() - startDate.getTime()) / (365 * msPerDay)) + 1);
            } else {
                nextStart = new Date(currentStart.getTime() + intervalDays * msPerDay);
            }
            
            const nextEnd = endDate ? new Date(nextStart.getTime() + duration) : new Date(nextStart.getTime() + msPerDay);
            if (repeatEndDate && (nextStart > effectiveRangeEnd || nextEnd > repeatEndDate)) {
                if (lastOccurrence) {
                    lastOccurrence.isLastOccurrence = true;
                }
                break;
            }
            
            currentStart = nextStart;
            count++;
        }
        
        if (repeatEndDate && lastOccurrence && !lastOccurrence.isLastOccurrence) {
            const lastEnd = lastOccurrence.end ? new Date(lastOccurrence.end) : new Date(new Date(lastOccurrence.start).getTime() + msPerDay);
            if (Math.abs(lastEnd.getTime() - repeatEndDate.getTime()) < msPerDay) {
                lastOccurrence.isLastOccurrence = true;
            }
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
                isOriginal: chain.isOriginal,
                isLastOccurrence: chain.isLastOccurrence
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

function applyEventInset(element, event = null) {
    if (!element) return;
    
    const priority = event?.extendedProps?.priority !== undefined 
        ? event.extendedProps.priority 
        : parseInt(element.getAttribute('data-priority')) || 2;
    
    if (priority === 2) {
        element.style.setProperty('inset', '0px 10% 0px 0px', 'important');
    } else if (priority === 1) {
        element.style.setProperty('inset', '0 0 0 10%', 'important');
    } else {
        element.style.setProperty('inset', '0 0 0 0', 'important');
    }
}

function updateEventStyles() {
    if (!calendar) return;
    
    setTimeout(() => {
        const events = calendar.getEvents();
        events.forEach(event => {
            if (event.extendedProps?.isOccurrence) return;
            if (event.el) {
                applyEventInset(event.el, event);
            }
        });
    }, 100);
}

function recalculatePriorities(chains) {
    return chains.map(chain => {
        const overlapping = findOverlappingChains(chains, chain.start, chain.end, chain.id);
        const priority = calculateNewPriority(chain, overlapping);
        return {
            ...chain,
            priority: priority
        };
    });
}

window.handleManagedChainsData = function(data) {
    if (chainsPromiseResolve) {
        cachedChains = data;
        cachedChains = recalculatePriorities(cachedChains);
        chainsPromiseResolve(cachedChains);
        chainsPromiseResolve = null;
    }
};

window.handleManagedChainsSaved = function(success) {
    if (savePromiseResolve) {
        savePromiseResolve(success);
        savePromiseResolve = null;
    }
};

async function loadChains() {
    const socket = getSocket();
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        if (cachedChains.length > 0) {
            return recalculatePriorities(cachedChains);
        }
        return cachedChains;
    }

    return new Promise((resolve) => {
        chainsPromiseResolve = resolve;
        socket.send(JSON.stringify({event: "request_managed_chains", chain_name: getSelectedChain()}));

        setTimeout(() => {
            if (chainsPromiseResolve === resolve) {
                chainsPromiseResolve = null;
                if (cachedChains.length > 0) {
                    resolve(recalculatePriorities(cachedChains));
                } else {
                    resolve(cachedChains);
                }
            }
        }, 5000);
    });
}

async function saveChains(chains) {
    if (!getSelectedChain()) {
        showError('Select a chain first');
        return;
    }
    cachedChains = chains;
    const socket = getSocket();
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        console.error('WebSocket not connected, cannot save managed chains');
        return;
    }

    return new Promise((resolve) => {
        savePromiseResolve = resolve;
        socket.send(JSON.stringify({event: "save_managed_chains", chain_name: getSelectedChain(), data: chains}));

        setTimeout(() => {
            if (savePromiseResolve === resolve) {
                savePromiseResolve = null;
                resolve(false);
            }
        }, 5000);
    });
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
    const isFirst = index === 0;
    const waitOption = isFirst ? '' : `<option value="wait" ${stepType === 'wait' ? 'selected' : ''}>wait</option>`;
    
    stepDiv.innerHTML = `
        <div class="step-controls">
            <select class="step-type">
                <option value="user" ${stepType === 'user' ? 'selected' : ''}>user</option>
                <option value="user_group" ${stepType === 'user_group' ? 'selected' : ''}>user_group</option>
                <option value="group" ${stepType === 'group' ? 'selected' : ''}>group</option>
                ${waitOption}
                <option value="chain" ${stepType === 'chain' ? 'selected' : ''}>chain</option>
            </select>
            <input type="text" class="step-value" placeholder="Enter value" value="${stepValue}" list="step-options-${index !== null ? index : Date.now()}">
            <datalist id="step-options-${index !== null ? index : Date.now()}"></datalist>
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
            valueInput.placeholder = 'e.g. 5m';
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
        stepsContainer.appendChild(createStepElement(null, 0));
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

function calculateNewPriority(chain, overlappingChains) {
    if (overlappingChains.length === 0) {
        return 2;
    }
    
    const hasRepeat = chain.repeat ? true : false;
    const overlappingHasRepeat = overlappingChains.some(c => c.repeat);
    
    if (hasRepeat || overlappingHasRepeat) {
        return hasRepeat ? 2 : 1;
    }
    
    const chainId = chain.id || '';
    const overlappingIds = overlappingChains.map(c => c.id || '').filter(id => id);
    
    if (overlappingIds.length === 0) {
        return 2;
    }
    
    const maxId = overlappingIds.reduce((max, id) => id > max ? id : max, overlappingIds[0]);
    return chainId >= maxId ? 1 : 2;
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
    
    const chains = await loadChains();
    const droppedOriginalId = droppedEvent.extendedProps?.originalId || droppedEvent.id;
    const droppedChainIndex = chains.findIndex(c => c.id === droppedOriginalId);
    
    if (droppedChainIndex === -1) {
        droppedEvent.setExtendedProp('priority', 2);
        return;
    }
    
    const droppedChain = chains[droppedChainIndex];
    
    if (overlappingEvents.length === 0) {
        droppedEvent.setExtendedProp('priority', 2);
        droppedChain.priority = 2;
        if (droppedEvent.el) {
            applyEventInset(droppedEvent.el, droppedEvent);
        }
        await saveChains(chains);
        return;
    }
    
    const overlappingChains = overlappingEvents.map(evt => {
        const originalId = evt.extendedProps?.originalId || evt.id;
        return chains.find(c => c.id === originalId);
    }).filter(c => c);
    
    const newPriority = calculateNewPriority(droppedChain, overlappingChains);
    droppedEvent.setExtendedProp('priority', newPriority);
    droppedChain.priority = newPriority;
    
    if (droppedEvent.el) {
        applyEventInset(droppedEvent.el, droppedEvent);
    }
    
    for (const overlappingEvent of overlappingEvents) {
        const originalId = overlappingEvent.extendedProps?.originalId || overlappingEvent.id;
        const overlappingChainIndex = chains.findIndex(c => c.id === originalId);
        if (overlappingChainIndex !== -1) {
            const overlappingChain = chains[overlappingChainIndex];
            const otherOverlapping = [droppedChain, ...overlappingChains.filter(c => c.id !== originalId)];
            const otherPriority = calculateNewPriority(overlappingChain, otherOverlapping);
            overlappingEvent.setExtendedProp('priority', otherPriority);
            overlappingChain.priority = otherPriority;
            
            if (overlappingEvent.el) {
                applyEventInset(overlappingEvent.el, overlappingEvent);
            }
        }
    }
    
    await saveChains(chains);
}

function formatDateTime(date) {
    const timezone = getEffectiveTimezone();
    const pad = (n) => n.toString().padStart(2, '0');
    if (typeof luxon === 'undefined') {
        const d = new Date(date);
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}, ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    }
    const dt = luxon.DateTime.fromISO(new Date(date).toISOString(), { zone: 'utc' }).setZone(timezone);
    return `${dt.year}-${pad(dt.month)}-${pad(dt.day)}, ${pad(dt.hour)}:${pad(dt.minute)}`;
}

function parseDateTime(dateStr) {
    const match = dateStr.match(/(\d{4})-(\d{2})-(\d{2}),\s*(\d{2}):(\d{2})/);
    if (!match) return null;
    const [, year, month, day, hour, minute] = match;
    const timezone = getEffectiveTimezone();
    if (typeof luxon === 'undefined') {
        return new Date(+year, +month - 1, +day, +hour, +minute).toISOString();
    }
    return luxon.DateTime.fromObject(
        { year: +year, month: +month, day: +day, hour: +hour, minute: +minute, second: 0 },
        { zone: timezone }
    ).toUTC().toISO();
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
        modalTitle.textContent = 'New duty';
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
    let steps = getSteps();

    if (steps.length > 0) {
        const lastStep = steps[steps.length - 1];
        const lastStepType = Object.keys(lastStep)[0];
        if (lastStepType === 'wait') {
            steps = steps.slice(0, -1);
        }
    }
    if (steps.length === 0 || steps.every(step => Object.keys(step)[0] === 'wait')) {
        showError('No steps added');
        return;
    }

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
        }
        
        const index = chains.findIndex(c => c.id === currentChainId);
        if (index !== -1) {
            const existingChain = chains[index];
            const updatedChain = {
                ...chains[index],
                start,
                end: end || null,
                repeat: repeat || null,
                repeatEnd: existingChain.repeatEnd || null,
                steps: steps.length > 0 ? steps : null
            };
            const priority = calculateNewPriority(updatedChain, overlapping);
            updatedChain.priority = priority;
            
            for (const overlappingChain of overlapping) {
                const overlappingIndex = chains.findIndex(c => c.id === overlappingChain.id);
                if (overlappingIndex !== -1) {
                    const otherOverlapping = [updatedChain, ...overlapping.filter(c => c.id !== overlappingChain.id)];
                    const otherPriority = calculateNewPriority(overlappingChain, otherOverlapping);
                    chains[overlappingIndex].priority = otherPriority;
                }
            }
            
            chains[index] = updatedChain;
        }
        
        await saveChains(chains);
        const expandedChains = getExpandedChains(chains);
        calendar.removeAllEvents();
        calendar.addEventSource(expandedChains);
        monthCalendar.removeAllEvents();
        monthCalendar.addEventSource(expandedChains);
        updateEventStyles();
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
        }
        
        const newChain = {
            id: generateId(),
            title: '',
            start,
            end: end || null,
            repeat: repeat || null,
            steps: steps.length > 0 ? steps : null
        };
        const newPriority = calculateNewPriority(newChain, overlapping);
        newChain.priority = newPriority;
        
        for (const overlappingChain of overlapping) {
            const overlappingIndex = chains.findIndex(c => c.id === overlappingChain.id);
            if (overlappingIndex !== -1) {
                const otherOverlapping = [newChain, ...overlapping.filter(c => c.id !== overlappingChain.id)];
                const otherPriority = calculateNewPriority(overlappingChain, otherOverlapping);
                chains[overlappingIndex].priority = otherPriority;
            }
        }
        
        chains.push(newChain);
    }

    await saveChains(chains);
    const expandedChains = getExpandedChains(chains);
    calendar.removeAllEvents();
    calendar.addEventSource(expandedChains);
    monthCalendar.removeAllEvents();
    monthCalendar.addEventSource(expandedChains);
    updateEventStyles();
    closeChainEditModal();
}

async function deleteChain() {
    if (!currentChainId) return;

    try {
        const chains = await loadChains();
        const filtered = chains.filter(c => c.id !== currentChainId);
        await saveChains(filtered);
        const expandedChains = getExpandedChains(filtered);
        if (calendar) {
            calendar.removeAllEvents();
            calendar.addEventSource(expandedChains);
        }
        if (monthCalendar) {
            monthCalendar.removeAllEvents();
            monthCalendar.addEventSource(expandedChains);
        }
        updateEventStyles();
        closeChainEditModal();
    } catch (error) {
        console.error('Failed to delete chain:', error);
    }
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

function getTimezoneMode() {
    const saved = localStorage.getItem('managed_chains_timezone_mode');
    const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const configTz = chainsConfig.timezone;
    if (saved === 'user' || saved === 'config' || saved === 'utc') {
        return saved;
    }
    if (userTz && userTz !== 'UTC') {
        return 'user';
    }
    if (configTz && configTz !== 'UTC') {
        return 'config';
    }
    return 'utc';
}

function setTimezoneMode(mode) {
    localStorage.setItem('managed_chains_timezone_mode', mode);
}

function getEffectiveTimezone() {
    const mode = getTimezoneMode();
    if (mode === 'user') {
        return Intl.DateTimeFormat().resolvedOptions().timeZone;
    } else if (mode === 'config') {
        return chainsConfig.timezone || 'UTC';
    }
    return 'UTC';
}

function getSelectedChain() {
    return localStorage.getItem('managed_chains_selected_chain') || '';
}

function setSelectedChain(chainName) {
    localStorage.setItem('managed_chains_selected_chain', chainName);
}

function showCalendarContainer(show) {
    const el = document.getElementById('calendar-container');
    if (el) {
        el.classList.toggle('chains-calendar-hidden', !show);
    }
}

function updateChainSelector() {
    const selector = document.getElementById('chain-select');
    if (!selector) return;

    selector.innerHTML = '';

    const managedChains = chainsConfig.managed_chains || [];
    const currentChain = getSelectedChain();

    const emptyOption = document.createElement('option');
    emptyOption.value = '';
    emptyOption.textContent = 'Select chain';
    if (!currentChain) {
        emptyOption.selected = true;
    }
    selector.appendChild(emptyOption);

    managedChains.forEach(chainName => {
        const option = document.createElement('option');
        option.value = chainName;
        option.textContent = chainName;
        if (currentChain === chainName) {
            option.selected = true;
        }
        selector.appendChild(option);
    });
}

function updateTimezoneSelector() {
    const selector = document.getElementById('timezone-select');
    if (!selector) return;
    
    selector.innerHTML = '';
    
    const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const configTz = chainsConfig.timezone;
    const currentMode = getTimezoneMode();
    
    if (userTz && userTz !== 'UTC') {
        const option = document.createElement('option');
        option.value = 'user';
        option.textContent = `${userTz} (user)`;
        if (currentMode === 'user') {
            option.selected = true;
        }
        selector.appendChild(option);
    }
    
    if (configTz && configTz !== 'UTC') {
        const option = document.createElement('option');
        option.value = 'config';
        option.textContent = `${configTz} (config)`;
        if (currentMode === 'config') {
            option.selected = true;
        }
        selector.appendChild(option);
    }
    
    const utcOption = document.createElement('option');
    utcOption.value = 'utc';
    utcOption.textContent = 'UTC';
    if (currentMode === 'utc') {
        utcOption.selected = true;
    }
    selector.appendChild(utcOption);
}

async function updateCalendarTimezone() {
    if (!calendar || !monthCalendar) return;

    const timegridScroller = document.querySelector('#calendar .fc-timegrid-body .fc-scroller');
    const scrollTop = timegridScroller ? timegridScroller.scrollTop : 0;
    
    const timezone = getEffectiveTimezone();
    calendar.setOption('timeZone', timezone);
    monthCalendar.setOption('timeZone', timezone);
    
    const chains = await loadChains();
    const expandedChains = getExpandedChains(chains);
    calendar.removeAllEvents();
    calendar.addEventSource(expandedChains);
    monthCalendar.removeAllEvents();
    monthCalendar.addEventSource(expandedChains);
    updateEventStyles();
    
    calendar.render();
    monthCalendar.render();

    if (timegridScroller) {
        requestAnimationFrame(() => {
            timegridScroller.scrollTop = scrollTop;
        });
    }
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
    
    const weekStart = new Date(calendar.view.activeStart);
    weekStart.setHours(0, 0, 0, 0);
    const weekEnd = new Date(calendar.view.activeEnd);
    weekEnd.setHours(0, 0, 0, 0);
    
    const dayCells = monthCalendar.el.querySelectorAll('.fc-daygrid-day:not(.fc-day-other)');
    dayCells.forEach(cell => {
        const dateStr = cell.getAttribute('data-date');
        if (!dateStr) return;
        
        const cellDate = new Date(dateStr + 'T00:00:00');
        cellDate.setHours(0, 0, 0, 0);
        if (cellDate >= weekStart && cellDate < weekEnd) {
            cell.classList.add('current-week');
        } else {
            cell.classList.remove('current-week');
        }
    });
}

function bindCalendarNavButtons() {
    const prevBtn = document.getElementById('calendar-prev');
    const nextBtn = document.getElementById('calendar-next');
    const todayBtn = document.getElementById('calendar-today');

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

    if (todayBtn && !todayBtn.hasAttribute('data-listener-attached')) {
        todayBtn.setAttribute('data-listener-attached', 'true');
        todayBtn.addEventListener('click', () => {
            calendar.today();
            setTimeout(() => updateWeekNumberDisplay(), 50);
        });
    }
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
            updateTimezoneSelector();
            const timezone = getEffectiveTimezone();
            calendar.setOption('timeZone', timezone);
            monthCalendar.setOption('timeZone', timezone);
            calendar.render();
            monthCalendar.render();
            
            bindCalendarNavButtons();
            
            setTimeout(() => {
                calendar.updateSize();
                monthCalendar.updateSize();
            }, 100);
            return;
        }
        
        const firstDay = parseWeekStart(chainsConfig.week_start);
        const timezone = getEffectiveTimezone();

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
            nowIndicator: true,
            slotMinHeight: 60,
            scrollTimeReset: false,
            allDaySlot: false,
            firstDay: firstDay,
            timeZone: timezone,
            weekNumbers: true,
            weekNumberCalculation: 'ISO',
            dayHeaderFormat: { weekday: 'short', day: 'numeric', omitCommas: false },
            slotLabelFormat: {
                hour: '2-digit',
                minute: '2-digit',
                hour12: false
            },
            slotDuration: '00:30:00',
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
                applyEventInset(el, arg.event);
                
                const isOriginal = arg.event.extendedProps?.isOriginal;
                if ((isOccurrence || isOriginal) && hasRepeat) {
                    setTimeout(() => {
                        if (el.querySelector('.fc-event-repeat-end-btn')) {
                            return;
                        }
                        
                        const isLastOccurrence = arg.event.extendedProps?.isLastOccurrence;
                        const repeatEndBtn = document.createElement('button');
                        repeatEndBtn.className = 'fc-event-repeat-end-btn';
                        if (isLastOccurrence) {
                            repeatEndBtn.classList.add('active');
                        }
                        repeatEndBtn.innerHTML = 'End';
                        repeatEndBtn.title = isLastOccurrence ? 'Remove repeat end' : 'Set repeat end after this event';
                        
                        repeatEndBtn.addEventListener('click', async (e) => {
                            e.stopPropagation();
                            e.preventDefault();
                            const originalId = arg.event.extendedProps?.originalId || arg.event.id;
                            
                            const chains = await loadChains();
                            const index = chains.findIndex(c => c.id === originalId);
                            
                            if (index !== -1) {
                                if (isLastOccurrence) {
                                    chains[index].repeatEnd = null;
                                } else {
                                    const eventEnd = arg.event.end || new Date(arg.event.start.getTime() + 24 * 60 * 60 * 1000);
                                    chains[index].repeatEnd = eventEnd.toISOString();
                                }
                                await saveChains(chains);
                                const expandedChains = getExpandedChains(chains);
                                calendar.removeAllEvents();
                                calendar.addEventSource(expandedChains);
                                monthCalendar.removeAllEvents();
                                monthCalendar.addEventSource(expandedChains);
                                updateEventStyles();
                            }
                        });
                        
                        if (isLastOccurrence) {
                            repeatEndBtn.style.display = 'block';
                        } else {
                            repeatEndBtn.style.display = 'none';
                            el.addEventListener('mouseenter', () => {
                                repeatEndBtn.style.setProperty('display', 'block', 'important');
                            });
                            
                        el.addEventListener('mouseleave', () => {
                            repeatEndBtn.style.setProperty('display', 'none', 'important');
                        });
                        }
                        
                        const eventMain = el.querySelector('.fc-event-main') || el;
                        eventMain.appendChild(repeatEndBtn);
                    }, 10);
                }
            },
            eventTimeFormat: {
                hour: '2-digit',
                minute: '2-digit',
                hour12: false
            },
            displayEventTime: false,
            events: expandedChains,

            select: function(info) {
                if (!getSelectedChain()) {
                    showError('Select a chain first');
                    calendar.unselect();
                    return;
                }
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
                    updateEventStyles();
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
                    updateEventStyles();
                }
            },

            datesSet: function() {
                updateWeekNumberDisplay();
                if (monthCalendar) {
                    monthCalendar.gotoDate(calendar.view.activeStart);
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
        timeZone: timezone,
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
            const cellDate = new Date(info.date);
            cellDate.setHours(0, 0, 0, 0);
            const weekStart = new Date(calendar.view.activeStart);
            weekStart.setHours(0, 0, 0, 0);
            const weekEnd = new Date(calendar.view.activeEnd);
            weekEnd.setHours(0, 0, 0, 0);
            
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
            updateEventStyles();
        }, 200);
        
        bindCalendarNavButtons();
        
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
        const existingSteps = stepsContainer.querySelectorAll('.step-item');
        const nextIndex = existingSteps.length;
        stepsContainer.appendChild(createStepElement(null, nextIndex));
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeChainEditModal();
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.classList.contains('visible')) {
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
                await loadChainsConfig();
                updateChainSelector();
                updateTimezoneSelector();
                if (getSelectedChain()) {
                    showCalendarContainer(true);
                    await initializeCalendars();
                    setTimeout(() => {
                        if (calendar) calendar.updateSize();
                        if (monthCalendar) monthCalendar.updateSize();
                    }, 100);
                } else {
                    showCalendarContainer(false);
                }
            }, 200);
        });

        const chainSelect = document.getElementById('chain-select');
        if (chainSelect) {
            chainSelect.addEventListener('change', async (e) => {
                const value = e.target.value;
                setSelectedChain(value);
                if (!value) {
                    showCalendarContainer(false);
                    return;
                }
                showCalendarContainer(true);
                if (!initialized || !calendar) {
                    await initializeCalendars();
                    setTimeout(() => {
                        if (calendar) calendar.updateSize();
                        if (monthCalendar) monthCalendar.updateSize();
                    }, 100);
                } else {
                    const chains = await loadChains();
                    const expandedChains = getExpandedChains(chains);
                    calendar.removeAllEventSources();
                    calendar.addEventSource(expandedChains);
                    monthCalendar.removeAllEventSources();
                    monthCalendar.addEventSource(expandedChains);
                    updateEventStyles();
                }
            });
        }
        
        const timezoneSelect = document.getElementById('timezone-select');
        if (timezoneSelect) {
            timezoneSelect.addEventListener('change', async (e) => {
                setTimezoneMode(e.target.value);
                await updateCalendarTimezone();
            });
        }

        chainsCloseBtn.addEventListener('click', () => {
            chainsModal.classList.remove('visible');
        });

        chainsModal.addEventListener('click', (e) => {
            if (e.target === chainsModal) {
                chainsModal.classList.remove('visible');
            }
        });

        document.addEventListener('keydown', (e) => {
            const chainModal = document.getElementById('chain-modal');
            if (chainModal && chainModal.classList.contains('visible')) {
                return;
            }
            if (e.key === 'Escape' && chainsModal.classList.contains('visible')) {
                chainsModal.classList.remove('visible');
            }
        });

        setupChainEditModalListeners();
        this.initialized = true;
    }
};
