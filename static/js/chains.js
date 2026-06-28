import {getSocket} from "./websocket.js";
import {getBaseUrl, parseWeekStart} from "./utils.js";
import {attachNavListener, getSharedCalendarOptions, updateMonthCalendarWeekHighlight} from "./calendar_shared.js";
import {getIsAuthenticated, onAuthChange} from "./auth.js";
import {
    captureCalendarViewAnchor,
    closeAllTimezoneMenus,
    ensureTimezoneSelectWidget,
    formatDateTime,
    getEffectiveTimezone as effectiveTimezone,
    onTimezoneChange,
    parseDateTime,
    reformatDateTimeInput,
    syncTimezoneMenuWidth,
    syncTimezoneSelects,
    updateTimezoneConfig,
} from "./ui_timezone.js";

let calendar = null;
let monthCalendar = null;
let eventOverlapObserver = null;
let currentChainId = null;
let chainsConfig = { users: [], user_groups: [], groups: [], chains: [], webhooks: [], week_start: "Mon", timezone: "UTC", messenger_type: "", user_timezone: null };
let initialized = false;
let cachedChains = [];
let chainsPromiseResolve = null;
let savePromiseResolve = null;

function getRepeatIntervalDays(repeat) {
    switch (repeat) {
        case 'daily': return 1;
        case 'weekly': return 7;
        case 'monthly': return 30;
        case 'yearly': return 365;
        default: return null;
    }
}

function daysInMonth(year, month) {
    return new Date(year, month, 0).getDate();
}

function getNextMonthly(baseStart, currentStart) {
    const year = currentStart.getMonth() === 11 ? currentStart.getFullYear() + 1 : currentStart.getFullYear();
    const month = currentStart.getMonth() === 11 ? 0 : currentStart.getMonth() + 1;
    const day = Math.min(baseStart.getDate(), daysInMonth(year, month + 1));
    return new Date(year, month, day,
        currentStart.getHours(), currentStart.getMinutes(), currentStart.getSeconds(), currentStart.getMilliseconds());
}

function getNextYearly(baseStart, currentStart) {
    const year = currentStart.getFullYear() + 1;
    let day = baseStart.getDate();
    const month = baseStart.getMonth();
    const isLeap = (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
    if (month === 1 && day === 29 && !isLeap) {
        day = 28;
    }
    return new Date(year, month, day,
        currentStart.getHours(), currentStart.getMinutes(), currentStart.getSeconds(), currentStart.getMilliseconds());
}

function getNextOccurrenceStart(baseStart, currentStart, repeat) {
    const msPerDay = 24 * 60 * 60 * 1000;
    switch (repeat) {
        case 'daily':
            return new Date(currentStart.getTime() + msPerDay);
        case 'weekly':
            return new Date(currentStart.getTime() + 7 * msPerDay);
        case 'monthly':
            return getNextMonthly(baseStart, currentStart);
        case 'yearly':
            return getNextYearly(baseStart, currentStart);
        default:
            return new Date(currentStart.getTime() + msPerDay);
    }
}

function advanceRepeatStart(chain, startDate, currentStart, intervalDays, msPerDay) {
    if (chain.repeat === 'monthly') {
        const nextStart = new Date(startDate);
        nextStart.setMonth(nextStart.getMonth() + Math.floor((currentStart.getTime() - startDate.getTime()) / (30 * msPerDay)) + 1);
        return nextStart;
    }
    if (chain.repeat === 'yearly') {
        const nextStart = new Date(startDate);
        nextStart.setFullYear(nextStart.getFullYear() + Math.floor((currentStart.getTime() - startDate.getTime()) / (365 * msPerDay)) + 1);
        return nextStart;
    }
    return new Date(currentStart.getTime() + intervalDays * msPerDay);
}

function pushOriginalIfInRange(chain, startDate, endDate, repeatEndDate, msPerDay, expandedEvents) {
    if (!repeatEndDate || (endDate ? endDate <= repeatEndDate : startDate <= repeatEndDate)) {
        const originalEvent = { ...chain, isOriginal: true };
        if (repeatEndDate) {
            const originalEnd = endDate ? endDate : new Date(startDate.getTime() + msPerDay);
            if (Math.abs(originalEnd.getTime() - repeatEndDate.getTime()) < msPerDay) {
                originalEvent.isLastOccurrence = true;
            }
        }
        expandedEvents.push(originalEvent);
    }
}

function occurrenceOverlapsRange(occurrenceStart, duration, repeatEndDate, rangeStart, rangeEnd) {
    const occurrenceEnd = new Date(occurrenceStart.getTime() + duration);
    if (repeatEndDate && occurrenceEnd > repeatEndDate) {
        return false;
    }
    return rangeStart < occurrenceEnd && rangeEnd > occurrenceStart;
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
        
        const intervalDays = getRepeatIntervalDays(chain.repeat);
        if (intervalDays === null) {
            expandedEvents.push(chain);
            return;
        }
        
        pushOriginalIfInRange(chain, startDate, endDate, repeatEndDate, msPerDay, expandedEvents);
        
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
            
            const nextStart = advanceRepeatStart(chain, startDate, currentStart, intervalDays, msPerDay);
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
        const priority = chain.priority ?? 2;
        const isOccurrence = !!chain.isOccurrence;
        
        return {
            ...chain,
            title: stepsText || chain.title || '',
            editable: !isOccurrence,
            startEditable: !isOccurrence,
            durationEditable: !isOccurrence,
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
            backgroundColor: chain.backgroundColor || getComputedStyle(document.documentElement).getPropertyValue('--chain-event-bg').trim(),
            borderColor: chain.borderColor || getComputedStyle(document.documentElement).getPropertyValue('--chain-event-border').trim()
        };
    }).sort((a, b) => {
        const timeDiff = new Date(a.start) - new Date(b.start);
        if (Math.abs(timeDiff) < 1000) {
            const priority1 = a.extendedProps?.priority ?? 2;
            const priority2 = b.extendedProps?.priority ?? 2;
            return priority2 - priority1;
        }
        return timeDiff;
    });
}

function getExpandedChains(chains) {
    return prepareEventsForCalendar(chains);
}

function shouldApplyVisualShift(eventLike) {
    return true;
}

function applyEventInset(element, event = null) {
    if (!element) return;
    
    const priority = event?.extendedProps?.priority ?? (Number.parseInt(element.dataset.priority) || 2);
    
    if (priority === 2) {
        element.style.setProperty('inset', '0px 10% 0px 0px', 'important');
    } else if (priority === 1) {
        element.style.setProperty('inset', '0 0 0 10%', 'important');
    } else {
        element.style.setProperty('inset', '0 0 0 0', 'important');
    }
}

function applyEventOverlapOffset(element) {
    if (!element) return;

    const harness = element.closest('.fc-timegrid-event-harness');
    applyHarnessOverlapOffset(harness);
}

function applyHarnessOverlapOffset(harness) {
    if (!harness) return;

    const left = parseFloat(harness.style.left);
    const right = parseFloat(harness.style.right);

    // FullCalendar positions the second overlapping event at 50%.
    // Shift it to 10% while keeping it inside the slot.
    if (Number.isFinite(left) && left > 10 && (!Number.isFinite(right) || right === 0)) {
        harness.style.setProperty('left', '0%', 'important');
        harness.style.setProperty('right', '0%', 'important');
    }
}

function setupEventOverlapObserver(rootElement) {
    if (eventOverlapObserver) {
        eventOverlapObserver.disconnect();
        eventOverlapObserver = null;
    }

    if (!rootElement || typeof MutationObserver === 'undefined') {
        return;
    }

    eventOverlapObserver = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (!(mutation.target instanceof HTMLElement)) {
                return;
            }

            const target = mutation.target;
            if (target.classList.contains('fc-timegrid-event-harness')) {
                applyHarnessOverlapOffset(target);
            }
        });
    });

    eventOverlapObserver.observe(rootElement, {
        subtree: true,
        attributes: true,
        attributeFilter: ['style']
    });

    rootElement.querySelectorAll('.fc-timegrid-event-harness').forEach((harness) => {
        applyHarnessOverlapOffset(harness);
    });
}

function updateEventStyles() {
    if (!calendar) return;
    
    setTimeout(() => {
        const events = calendar.getEvents();
        events.forEach(event => {
            if (event.extendedProps?.isOccurrence) return;
            if (event.el) {
                applyEventOverlapOffset(event.el);
                applyEventInset(event.el, event);
            }
        });
    }, 100);
}

function recalculatePriorities(chains) {
    return chains.map(chain => {
        const overlapping = findOverlappingChainsForChain(chains, chain, chain.id);
        const priority = calculateNewPriority(chain, overlapping);
        return {
            ...chain,
            priority: priority
        };
    });
}

function recalculatePrioritiesForChainIds(chains, chainIds) {
    const impactedIds = new Set(chainIds.filter(Boolean));

    if (impactedIds.size === 0) {
        return chains;
    }

    return chains.map(chain => {
        if (!impactedIds.has(chain.id)) {
            return chain;
        }

        const overlapping = findOverlappingChainsForChain(chains, chain, chain.id);
        return {
            ...chain,
            priority: calculateNewPriority(chain, overlapping)
        };
    });
}

function applyPriorityToEvent(event, chain) {
    event.setExtendedProp('priority', chain.priority ?? 2);
    if (event.el) {
        applyEventOverlapOffset(event.el);
        applyEventInset(event.el, event);
    }
}

function syncCalendarEventPriorities(chains, chainIds, preferredEvent = null) {
    if (!calendar) {
        return;
    }

    const impactedIds = new Set(chainIds.filter(Boolean));
    if (preferredEvent) {
        const preferredId = preferredEvent.extendedProps?.originalId || preferredEvent.id;
        impactedIds.add(preferredId);
    }

    const chainById = new Map(chains.map(chain => [chain.id, chain]));
    const allEvents = calendar.getEvents();

    for (const event of allEvents) {
        if (event.extendedProps?.isOccurrence) {
            continue;
        }

        const originalId = event.extendedProps?.originalId || event.id;
        if (!impactedIds.has(originalId)) {
            continue;
        }

        const chain = chainById.get(originalId);
        if (!chain) {
            continue;
        }

        applyPriorityToEvent(event, chain);
    }

    if (preferredEvent) {
        const preferredId = preferredEvent.extendedProps?.originalId || preferredEvent.id;
        const preferredChain = chainById.get(preferredId);
        if (preferredChain) {
            applyPriorityToEvent(preferredEvent, preferredChain);
        }
    }
}

globalThis.handleUiChainsData = function(data) {
    if (chainsPromiseResolve) {
        cachedChains = data;
        cachedChains = recalculatePriorities(cachedChains);
        chainsPromiseResolve(cachedChains);
        chainsPromiseResolve = null;
    }
};

globalThis.handleUiChainsSaved = function(success) {
    if (savePromiseResolve) {
        savePromiseResolve(success);
        savePromiseResolve = null;
    }
};

globalThis.handleUiChainsError = function() {
    if (chainsPromiseResolve) {
        chainsPromiseResolve([]);
        chainsPromiseResolve = null;
    }
    if (savePromiseResolve) {
        savePromiseResolve(false);
        savePromiseResolve = null;
    }
};

const CHAINS_TOGGLE_HTML =
    '<svg class="chains-icon" width="16" height="16" viewBox="0 0 13 15" fill="none" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M9.16667 0.5V3.16667M3.83333 0.5V3.16667M0.5 5.83333H12.5M1.83333 1.83333H11.1667C11.903 1.83333 12.5 2.43029 12.5 3.16667V12.5C12.5 13.2364 11.903 13.8333 11.1667 13.8333H1.83333C1.09695 13.8333 0.5 13.2364 0.5 12.5V3.16667C0.5 2.43029 1.09695 1.83333 1.83333 1.83333Z" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"/>' +
    '</svg>';

let footerToggleClickHandler = null;

function getPrivilegedFooterControlsContainer() {
    return document.getElementById("privileged-footer-controls");
}

function closeChainsModal() {
    const chainsModal = document.getElementById("chains-modal");
    chainsModal?.classList.remove("visible");
}

function mountFooterToggle() {
    if (document.getElementById("chains-toggle")) {
        return;
    }
    const container = getPrivilegedFooterControlsContainer();
    if (!container) {
        return;
    }
    const toggle = document.createElement("button");
    toggle.id = "chains-toggle";
    toggle.className = "control-btn";
    toggle.title = "UI Chains";
    toggle.type = "button";
    toggle.innerHTML = CHAINS_TOGGLE_HTML;
    footerToggleClickHandler = () => {
        if (!getIsAuthenticated()) {
            return;
        }
        openChainsModal();
    };
    toggle.addEventListener("click", footerToggleClickHandler);
    container.appendChild(toggle);
}

function unmountFooterToggle() {
    closeChainsModal();
    const toggle = document.getElementById("chains-toggle");
    if (!toggle) {
        return;
    }
    if (footerToggleClickHandler) {
        toggle.removeEventListener("click", footerToggleClickHandler);
        footerToggleClickHandler = null;
    }
    toggle.remove();
}

async function openChainsModal() {
    if (!getIsAuthenticated()) {
        return;
    }
    const chainsModal = document.getElementById("chains-modal");
    if (!chainsModal) {
        return;
    }
    chainsModal.classList.add("visible");

    await loadChainsConfig();

    if (typeof FullCalendar === "undefined") {
        console.error("FullCalendar is not loaded!");
        return;
    }

    setTimeout(async () => {
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
}

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
        socket.send(JSON.stringify({event: "request_ui_chains", chain_name: getSelectedChain()}));

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
    const recalculatedChains = recalculatePriorities(chains);
    chains.splice(0, chains.length, ...recalculatedChains);
    cachedChains = recalculatedChains;
    const socket = getSocket();
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        console.error('WebSocket not connected, cannot save ui chains');
        return;
    }

    return new Promise((resolve) => {
        savePromiseResolve = resolve;
        socket.send(JSON.stringify({event: "save_ui_chains", chain_name: getSelectedChain(), data: recalculatedChains}));

        setTimeout(() => {
            if (savePromiseResolve === resolve) {
                savePromiseResolve = null;
                resolve(false);
            }
        }, 5000);
    });
}

function generateId() {
    return crypto.randomUUID();
}

async function loadChainsConfig() {
    const response = await fetch(`${getBaseUrl()}/chains_config`, {credentials: "same-origin"});
    if (!response.ok) {
        throw new Error(`Failed to load chains config, status: ${response.status}`);
    }
    chainsConfig = await response.json();
    updateTimezoneConfig({
        configTimezone: chainsConfig.timezone,
        messengerType: chainsConfig.messenger_type,
        userTimezone: chainsConfig.user_timezone,
    });
}

function createStepElement(step = null, index = null) {
    const stepDiv = document.createElement('div');
    stepDiv.className = 'step-item';
    
    const stepType = step ? Object.keys(step)[0] : 'user';
    const stepValue = step ? step[stepType] : '';
    const isFirst = index === 0;
    const waitOption = isFirst ? '' : '<option value="wait">wait</option>';
    stepDiv.innerHTML = `
        <div class="step-controls">
            <select class="step-type">
                <option value="user">user</option>
                <option value="user_group">user_group</option>
                <option value="group">group</option>
                ${waitOption}
                <option value="chain">chain</option>
            </select>
            <div class="step-value-wrapper">
                <input type="text" class="step-value" placeholder="Enter value" autocomplete="off">
                <div class="step-value-options hidden"></div>
            </div>
            <button type="button" class="btn-remove-step chains-modal-close" aria-label="Remove step">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                    <path d="M1 1L11 11M11 1L1 11" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
            </button>
        </div>
    `;
    const typeSelect = stepDiv.querySelector('.step-type');
    const valueInput = stepDiv.querySelector('.step-value');
    const optionsEl = stepDiv.querySelector('.step-value-options');
    const valueWrapper = stepDiv.querySelector('.step-value-wrapper');
    const removeBtn = stepDiv.querySelector('.btn-remove-step');
    typeSelect.value = stepType;
    valueInput.value = stepValue;

    let activeOptionIndex = -1;

    function setActiveOption(index) {
        const optionNodes = optionsEl.querySelectorAll('.step-value-option');
        if (optionNodes.length === 0) {
            activeOptionIndex = -1;
            return;
        }
        const nextIndex = Math.max(0, Math.min(index, optionNodes.length - 1));
        activeOptionIndex = nextIndex;
        optionNodes.forEach((node, nodeIndex) => {
            node.classList.toggle('active', nodeIndex === nextIndex);
        });
    }

    function selectActiveOption() {
        const optionNodes = optionsEl.querySelectorAll('.step-value-option');
        if (activeOptionIndex < 0 || activeOptionIndex >= optionNodes.length) {
            return;
        }
        valueInput.value = optionNodes[activeOptionIndex].textContent;
        optionsEl.classList.add('hidden');
    }

    function getStepTypeOptions(stepTypeValue) {
        switch (stepTypeValue) {
            case 'user':
                return chainsConfig.users;
            case 'user_group':
                return chainsConfig.user_groups;
            case 'group':
                return chainsConfig.groups;
            case 'chain':
                return chainsConfig.chains;
            default:
                return [];
        }
    }

    function renderValueOptions(showAll = false) {
        const options = [...getStepTypeOptions(typeSelect.value)].sort((a, b) => a.localeCompare(b));
        const query = valueInput.value.trim().toLowerCase();
        const filtered = showAll || !query
            ? options
            : options.filter(option => option.toLowerCase().includes(query));

        optionsEl.innerHTML = '';
        filtered.forEach(option => {
            const optionEl = document.createElement('div');
            optionEl.className = 'step-value-option';
            optionEl.textContent = option;
            optionEl.addEventListener('mousedown', (event) => {
                event.preventDefault();
                valueInput.value = option;
                optionsEl.classList.add('hidden');
            });
            optionsEl.appendChild(optionEl);
        });
        activeOptionIndex = -1;

        if (filtered.length > 0 && typeSelect.value !== 'wait') {
            optionsEl.classList.remove('hidden');
        } else {
            optionsEl.classList.add('hidden');
        }
    }
    
    function updateOptions() {
        if (typeSelect.value === 'wait') {
            valueInput.placeholder = 'e.g. 5m';
            optionsEl.classList.add('hidden');
        } else {
            valueInput.placeholder = 'Enter value';
        }
    }
    
    typeSelect.addEventListener('change', () => {
        valueInput.value = '';
        updateOptions();
        renderValueOptions(true);
    });
    valueInput.addEventListener('focus', () => renderValueOptions(true));
    valueInput.addEventListener('click', () => renderValueOptions(true));
    valueInput.addEventListener('input', () => renderValueOptions(false));
    valueInput.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            if (optionsEl.classList.contains('hidden')) {
                renderValueOptions(true);
            }
            setActiveOption(activeOptionIndex + 1);
            return;
        }
        if (event.key === 'ArrowUp') {
            event.preventDefault();
            if (optionsEl.classList.contains('hidden')) {
                renderValueOptions(true);
            }
            if (activeOptionIndex < 0) {
                const optionNodes = optionsEl.querySelectorAll('.step-value-option');
                setActiveOption(optionNodes.length - 1);
            } else {
                setActiveOption(activeOptionIndex - 1);
            }
            return;
        }
        if (event.key === 'Enter') {
            if (!optionsEl.classList.contains('hidden') && activeOptionIndex >= 0) {
                event.preventDefault();
                selectActiveOption();
            }
            return;
        }
        if (event.key === 'Escape') {
            optionsEl.classList.add('hidden');
        }
    });
    valueInput.addEventListener('blur', () => {
        setTimeout(() => optionsEl.classList.add('hidden'), 100);
    });
    valueWrapper.addEventListener('mouseleave', () => {
        if (document.activeElement !== valueInput) {
            optionsEl.classList.add('hidden');
        }
    });
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

function findOverlappingChainsForChain(chains, candidateChain, excludeId = null) {
    if (!candidateChain?.start) {
        return [];
    }

    const normalizedCandidate = {
        ...candidateChain,
        end: candidateChain.end || null,
        repeat: candidateChain.repeat || null,
        repeatEnd: candidateChain.repeat ? (candidateChain.repeatEnd || null) : null
    };

    return chains.filter(chain => {
        if (excludeId && chain.id === excludeId) return false;
        if (!chain.start) return false;

        return doChainsOverlap(normalizedCandidate, chain);
    });
}

function doChainsOverlap(firstChain, secondChain) {
    const firstStart = new Date(firstChain.start);
    const firstEnd = firstChain.end ? new Date(firstChain.end) : new Date(firstStart.getTime() + 24 * 60 * 60 * 1000);
    const secondStart = new Date(secondChain.start);
    const secondEnd = secondChain.end ? new Date(secondChain.end) : new Date(secondStart.getTime() + 24 * 60 * 60 * 1000);

    return doesChainOverlapRange(firstChain, secondStart, secondEnd) ||
        doesChainOverlapRange(secondChain, firstStart, firstEnd);
}

function doesChainOverlapRange(chain, rangeStart, rangeEnd) {
    const msPerDay = 24 * 60 * 60 * 1000;
    const chainStart = new Date(chain.start);
    const chainEnd = chain.end ? new Date(chain.end) : new Date(chainStart.getTime() + msPerDay);
    const duration = chainEnd.getTime() - chainStart.getTime();

    if (!chain.repeat) {
        return rangeStart < chainEnd && rangeEnd > chainStart;
    }

    const repeatEndDate = chain.repeatEnd ? new Date(chain.repeatEnd) : null;
    if (repeatEndDate && chainStart >= repeatEndDate) {
        return false;
    }

    if (occurrenceOverlapsRange(chainStart, duration, repeatEndDate, rangeStart, rangeEnd)) {
        return true;
    }

    let currentStart = new Date(chainStart);
    const maxOccurrences = 520;

    for (let i = 0; i < maxOccurrences; i++) {
        const nextStart = getNextOccurrenceStart(chainStart, currentStart, chain.repeat);

        if (repeatEndDate) {
            const nextEnd = new Date(nextStart.getTime() + duration);
            if (nextEnd > repeatEndDate) {
                break;
            }
        }

        if (nextStart >= rangeEnd) {
            break;
        }

        if (occurrenceOverlapsRange(nextStart, duration, repeatEndDate, rangeStart, rangeEnd)) {
            return true;
        }

        currentStart = nextStart;
    }

    return false;
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
        return true;
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

    const chains = await loadChains();
    const droppedOriginalId = droppedEvent.extendedProps?.originalId || droppedEvent.id;
    const droppedChainIndex = chains.findIndex(c => c.id === droppedOriginalId);
    
    if (droppedChainIndex === -1) {
        droppedEvent.setExtendedProp('priority', 2);
        return;
    }
    
    const droppedChain = chains[droppedChainIndex];
    const previousOverlapping = findOverlappingChainsForChain(chains, droppedChain, droppedChain.id);
    const updatedDroppedChain = {
        ...droppedChain,
        start: droppedStart.toISOString(),
        end: droppedEnd ? droppedEnd.toISOString() : null
    };

    chains[droppedChainIndex] = updatedDroppedChain;

    const newOverlapping = findOverlappingChainsForChain(chains, updatedDroppedChain, updatedDroppedChain.id);
    const impactedIds = [
        updatedDroppedChain.id,
        ...previousOverlapping.map(chain => chain.id),
        ...newOverlapping.map(chain => chain.id)
    ];

    const updatedChains = recalculatePrioritiesForChainIds(chains, impactedIds);
    syncCalendarEventPriorities(updatedChains, impactedIds, droppedEvent);

    chains.splice(0, chains.length, ...updatedChains);
    await saveChains(chains);
}

function toggleRepeatUntilVisibility() {
    const repeatSelect = document.getElementById('chain-repeat');
    const untilGroup = document.getElementById('chain-until-group');
    const untilInput = document.getElementById('chain-until');
    const hasRepeat = !!repeatSelect?.value;

    if (!untilGroup || !untilInput) return;

    untilGroup.classList.toggle('hidden', !hasRepeat);
    untilGroup.style.display = hasRepeat ? 'block' : 'none';
    if (!hasRepeat) {
        untilInput.value = '';
    }
}

function openChainEditModal(chainData = null) {
    const modal = document.getElementById('chain-modal');
    const modalTitle = document.getElementById('modal-title');
    const { startInput, endInput, repeatSelect, untilInput } = getChainModalInputs();
    const deleteBtn = document.getElementById('delete-chain-btn');

    if (chainData) {
        currentChainId = chainData.id;
        modalTitle.textContent = 'Edit shift';
        startInput.value = formatDateTime(chainData.start, getEffectiveTimezone());
        endInput.value = chainData.end ? formatDateTime(chainData.end, getEffectiveTimezone()) : '';
        repeatSelect.value = chainData.repeat || '';
        untilInput.value = chainData.repeatEnd ? formatDateTime(chainData.repeatEnd, getEffectiveTimezone()) : '';
        renderSteps(chainData.steps || []);
        deleteBtn.classList.remove('hidden');
    } else {
        currentChainId = null;
        modalTitle.textContent = 'New shift';
        startInput.value = '';
        endInput.value = '';
        repeatSelect.value = '';
        untilInput.value = '';
        renderSteps([]);
        deleteBtn.classList.add('hidden');
    }

    toggleRepeatUntilVisibility();
    modal.classList.add('visible');
}

function getChainModalInputs() {
    return {
        startInput: document.getElementById('chain-start'),
        endInput: document.getElementById('chain-end'),
        repeatSelect: document.getElementById('chain-repeat'),
        untilInput: document.getElementById('chain-until'),
    };
}

function refreshCalendarEvents(expandedChains) {
    if (calendar) {
        calendar.removeAllEvents();
        calendar.addEventSource(expandedChains);
    }
    if (monthCalendar) {
        monthCalendar.removeAllEvents();
        monthCalendar.addEventSource(expandedChains);
    }
    updateEventStyles();
}

async function handleEventTimeChange(info) {
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
        chains[index].priority = info.event.extendedProps?.priority ?? 2;
        await persistChainsAndRerender(chains);
    }
}

function closeChainEditModal() {
    const modal = document.getElementById('chain-modal');
    modal.classList.remove('visible');
    currentChainId = null;
}

async function persistChainsAndRerender(chains) {
    await saveChains(chains);
    refreshCalendarEvents(getExpandedChains(chains));
}

function stripTrailingWaitSteps(steps) {
    if (steps.length === 0) {
        return steps;
    }
    const lastStepType = Object.keys(steps[steps.length - 1])[0];
    if (lastStepType === 'wait') {
        return steps.slice(0, -1);
    }
    return steps;
}

function hasActionableSteps(steps) {
    return steps.length > 0 && !steps.every(step => Object.keys(step)[0] === 'wait');
}

function validateRepeatEndBoundary(repeat, untilStr, start, end) {
    if (!repeat || !untilStr) {
        return null;
    }
    const repeatEnd = parseDateTime(untilStr, getEffectiveTimezone());
    if (!repeatEnd) {
        return null;
    }
    const minRepeatBoundary = new Date(end || start);
    if (new Date(repeatEnd) < minRepeatBoundary) {
        showError(`Until must be greater than or equal to ${end ? 'End' : 'Start'}`);
        return null;
    }
    return repeatEnd;
}

function validateChainInput() {
    const { startInput, endInput, repeatSelect, untilInput } = getChainModalInputs();

    const startStr = startInput.value.trim();
    const endStr = endInput.value.trim();
    const repeat = repeatSelect.value;
    const untilStr = untilInput.value.trim();
    let steps = stripTrailingWaitSteps(getSteps());

    if (!hasActionableSteps(steps)) {
        showError('No steps provided');
        return null;
    }

    if (!startStr) return null;

    const start = parseDateTime(startStr, getEffectiveTimezone());
    if (!start) return null;

    const end = endStr ? parseDateTime(endStr, getEffectiveTimezone()) : null;
    const repeatEnd = validateRepeatEndBoundary(repeat, untilStr, start, end);
    if (repeat && untilStr && repeatEnd === null) return null;

    return {
        start,
        end,
        repeat: repeat || null,
        repeatEnd: repeat ? (repeatEnd || null) : null,
        steps: steps.length > 0 ? steps : null,
    };
}

async function saveChain() {
    const input = validateChainInput();
    if (!input) return;

    const { start, end, repeat, repeatEnd, steps } = input;
    const chains = await loadChains();

    if (currentChainId) {
        const candidateChain = {
            id: currentChainId,
            start,
            end: end || null,
            repeat: repeat || null,
            repeatEnd: repeat ? (repeatEnd || null) : null
        };
        const overlapping = findOverlappingChainsForChain(chains, candidateChain, currentChainId);
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
            const previousOverlapping = findOverlappingChainsForChain(chains, existingChain, currentChainId);
            const updatedChain = {
                ...chains[index],
                start,
                end: end || null,
                repeat: repeat || null,
                repeatEnd: repeat ? (repeatEnd || null) : null,
                steps: steps.length > 0 ? steps : null
            };
            chains[index] = updatedChain;
            const impactedIds = [
                currentChainId,
                ...previousOverlapping.map(chain => chain.id),
                ...overlapping.map(chain => chain.id)
            ];
            const recalculatedChains = recalculatePrioritiesForChainIds(chains, impactedIds);
            chains.splice(0, chains.length, ...recalculatedChains);
        }
        
        await persistChainsAndRerender(chains);
        closeChainEditModal();
        return;
    } else {
        const candidateChain = {
            start,
            end: end || null,
            repeat: repeat || null,
            repeatEnd: repeat ? (repeatEnd || null) : null
        };
        const overlapping = findOverlappingChainsForChain(chains, candidateChain);
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
            repeatEnd: repeat ? (repeatEnd || null) : null,
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

    await persistChainsAndRerender(chains);
    closeChainEditModal();
}

async function deleteChain() {
    if (!currentChainId) return;

    try {
        const chains = await loadChains();
        const filtered = chains.filter(c => c.id !== currentChainId);
        await persistChainsAndRerender(filtered);
        closeChainEditModal();
    } catch (error) {
        console.error('Failed to delete chain:', error);
    }
}

function getEffectiveTimezone() {
    return effectiveTimezone(chainsConfig.timezone, chainsConfig.user_timezone);
}

function getSelectedChain() {
    return localStorage.getItem('ui_chains_selected_chain') || '';
}

function setSelectedChain(chainName) {
    localStorage.setItem('ui_chains_selected_chain', chainName);
}

function showCalendarContainer(show) {
    const el = document.getElementById('calendar-container');
    if (el) {
        el.classList.toggle('chains-calendar-hidden', !show);
    }
    const todayBtn = document.getElementById('calendar-today');
    if (todayBtn) {
        todayBtn.hidden = !show;
    }
}

function syncChainSelectWidget() {
    const selector = document.getElementById('chain-select');
    if (!selector) return;

    const widget = ensureTimezoneSelectWidget(selector);
    const trigger = widget.querySelector(".timezone-select-trigger");
    const triggerContent = widget.querySelector(".timezone-select-trigger-content");
    const menu = widget.querySelector(".timezone-select-menu");
    const selectedOption = selector.options[selector.selectedIndex];
    const label = selectedOption?.textContent || "Select chain";

    triggerContent.replaceChildren();
    const name = document.createElement("span");
    name.className = "timezone-select-name";
    name.textContent = label;
    triggerContent.appendChild(name);
    trigger.setAttribute("aria-label", `Chain: ${label}`);

    menu.replaceChildren();
    for (const option of selector.options) {
        const item = document.createElement("li");
        item.className = "timezone-select-option";
        if (option.selected) {
            item.classList.add("selected");
            item.setAttribute("aria-selected", "true");
        } else {
            item.setAttribute("aria-selected", "false");
        }
        item.setAttribute("role", "option");
        item.dataset.value = option.value;

        const body = document.createElement("div");
        body.className = "timezone-select-option-body timezone-select-option-body--single";
        const optionName = document.createElement("span");
        optionName.className = "timezone-select-name";
        optionName.textContent = option.textContent;
        body.appendChild(optionName);
        item.appendChild(body);

        item.addEventListener("click", (event) => {
            event.stopPropagation();
            closeAllTimezoneMenus();
            selector.value = option.value;
            selector.dispatchEvent(new Event("change", {bubbles: true}));
            syncChainSelectWidget();
        });
        menu.appendChild(item);
    }
    syncTimezoneMenuWidth(widget);
}

function updateChainSelector() {
    const selector = document.getElementById('chain-select');
    if (!selector) return;

    selector.innerHTML = '';

    const uiChains = chainsConfig.ui_chains || [];
    const savedChain = getSelectedChain();
    const currentChain = uiChains.includes(savedChain) ? savedChain : '';

    if (currentChain !== savedChain) {
        setSelectedChain('');
    }

    const emptyOption = document.createElement('option');
    emptyOption.value = '';
    emptyOption.textContent = 'Select chain';
    if (!currentChain) {
        emptyOption.selected = true;
    }
    selector.appendChild(emptyOption);

    uiChains.forEach(chainName => {
        const option = document.createElement('option');
        option.value = chainName;
        option.textContent = chainName;
        if (currentChain === chainName) {
            option.selected = true;
        }
        selector.appendChild(option);
    });

    syncChainSelectWidget();
}

function updateTimezoneSelector() {
    syncTimezoneSelects(chainsConfig.timezone, chainsConfig.messenger_type, chainsConfig.user_timezone);
}

function applySharedCalendarOptions() {
    const firstDay = parseWeekStart(chainsConfig.week_start);
    const timezone = getEffectiveTimezone();
    for (const cal of [calendar, monthCalendar]) {
        cal.setOption('firstDay', firstDay);
        cal.setOption('timeZone', timezone);
    }
}

function refreshChainModalDateTimes({previousTimezone, configTimezone, userTimezone}) {
    const modal = document.getElementById('chain-modal');
    if (!modal?.classList.contains('visible')) {
        return;
    }
    reformatDateTimeInput(document.getElementById('chain-start'), previousTimezone, configTimezone, userTimezone);
    reformatDateTimeInput(document.getElementById('chain-end'), previousTimezone, configTimezone, userTimezone);
    reformatDateTimeInput(document.getElementById('chain-until'), previousTimezone, configTimezone, userTimezone);
}

async function updateCalendarTimezone() {
    const modal = document.getElementById('chains-modal');
    if (!modal?.classList.contains('visible') || !initialized || !calendar || !monthCalendar) {
        return;
    }

    const calendarEl = document.getElementById('calendar');
    const monthCalendarEl = document.getElementById('month-calendar');
    if (!calendarEl || !monthCalendarEl) {
        return;
    }

    const timegridScroller = document.querySelector('#calendar .fc-timegrid-body .fc-scroller');
    const scrollTop = timegridScroller ? timegridScroller.scrollTop : 0;
    const anchorDate = captureCalendarViewAnchor(calendar);
    const firstDay = parseWeekStart(chainsConfig.week_start);
    const timezone = getEffectiveTimezone();

    if (eventOverlapObserver) {
        eventOverlapObserver.disconnect();
        eventOverlapObserver = null;
    }

    calendar.destroy();
    monthCalendar.destroy();

    const chains = await loadChains();
    const expandedChains = getExpandedChains(chains);

    const calendarOptions = buildMainCalendarOptions(expandedChains, firstDay, timezone);
    const monthOptions = buildMonthCalendarOptions(expandedChains, firstDay, timezone);
    if (anchorDate) {
        calendarOptions.initialDate = anchorDate;
        monthOptions.initialDate = anchorDate;
    }

    calendar = new FullCalendar.Calendar(calendarEl, calendarOptions);
    monthCalendar = new FullCalendar.Calendar(monthCalendarEl, monthOptions);
    calendar.render();
    monthCalendar.render();
    setupEventOverlapObserver(calendarEl);

    if (anchorDate) {
        calendar.gotoDate(anchorDate);
        monthCalendar.gotoDate(anchorDate);
    }

    bindCalendarNavButtons();
    updateWeekNumberDisplay();
    updateCurrentWeekHighlight();
    updateEventStyles();

    setTimeout(() => {
        calendar.updateSize();
        monthCalendar.updateSize();
        if (timegridScroller) {
            timegridScroller.scrollTop = scrollTop;
        }
    }, 50);
}

function updateWeekNumberDisplay() {
    if (!calendar) return;
    
    const weekNumber = calendar.view.dateEnv.computeWeekNumber(calendar.view.currentStart);
    const weekNumberDisplay = document.getElementById('week-number-display');
    
    if (weekNumberDisplay) {
        weekNumberDisplay.textContent = `Week ${weekNumber}`;
    }
}

function updateCurrentWeekHighlight() {
    updateMonthCalendarWeekHighlight(calendar, monthCalendar);
}

async function setRepeatEndFromEvent(event, isLastOccurrence) {
    const originalId = event.extendedProps?.originalId || event.id;
    const chains = await loadChains();
    const index = chains.findIndex(c => c.id === originalId);
    if (index === -1) {
        return;
    }
    if (isLastOccurrence) {
        chains[index].repeatEnd = null;
    } else {
        const eventEnd = event.end || new Date(event.start.getTime() + 24 * 60 * 60 * 1000);
        chains[index].repeatEnd = eventEnd.toISOString();
    }
    await persistChainsAndRerender(chains);
}

function mountRepeatEndButton(el, event) {
    if (el.querySelector('.fc-event-repeat-end-btn')) {
        return;
    }

    const isLastOccurrence = event.extendedProps?.isLastOccurrence;
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
        await setRepeatEndFromEvent(event, isLastOccurrence);
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
}

function styleMountedEvent(el, event) {
    const hasRepeat = event.extendedProps?.repeat;
    const priority = event.extendedProps?.priority ?? 2;

    for (let i = 1; i <= 2; i++) {
        el.classList.remove(`fc-event-priority-${i}`);
    }
    el.classList.remove('fc-event-repeat-series', 'fc-event-regular-series');

    el.classList.add(`fc-event-priority-${priority}`);
    el.classList.add(hasRepeat ? 'fc-event-repeat-series' : 'fc-event-regular-series');
    el.dataset.priority = priority.toString();
    el.style.zIndex = 3 - priority;
    if (shouldApplyVisualShift(event)) {
        applyEventOverlapOffset(el);
        applyEventInset(el, event);
    }
}

function buildMainCalendarOptions(expandedChains, firstDay, timezone) {
    return {
        initialView: 'timeGridWeek',
        headerToolbar: false,
        nowIndicator: true,
        slotMinHeight: 60,
        scrollTimeReset: false,
        allDaySlot: false,
        ...getSharedCalendarOptions(firstDay, timezone),
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
                const priority1 = event1.extendedProps?.priority ?? 2;
                const priority2 = event2.extendedProps?.priority ?? 2;
                return priority2 - priority1;
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
            const isOriginal = arg.event.extendedProps?.isOriginal;

            styleMountedEvent(el, arg.event);

            if ((isOccurrence || isOriginal) && hasRepeat) {
                setTimeout(() => mountRepeatEndButton(el, arg.event), 10);
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
            document.getElementById('chain-start').value = formatDateTime(info.start, getEffectiveTimezone());
            if (info.end) {
                document.getElementById('chain-end').value = formatDateTime(info.end, getEffectiveTimezone());
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

        eventDrop: handleEventTimeChange,

        eventResize: handleEventTimeChange,

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
    };
}

function buildMonthCalendarOptions(expandedChains, firstDay, timezone) {
    return {
        initialView: 'dayGridMonth',
        headerToolbar: {
            left: 'title',
            center: '',
            right: 'prev,next'
        },
        ...getSharedCalendarOptions(firstDay, timezone),
        height: 'auto',
        fixedWeekCount: false,
        showNonCurrentDates: false,
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

        datesSet: function() {
            setTimeout(() => {
                updateCurrentWeekHighlight();
            }, 50);
        }
    };
}

function bindCalendarNavButtons() {
    attachNavListener(document.getElementById('calendar-prev'), () => {
        calendar.prev();
        setTimeout(() => updateWeekNumberDisplay(), 50);
    });
    attachNavListener(document.getElementById('calendar-next'), () => {
        calendar.next();
        setTimeout(() => updateWeekNumberDisplay(), 50);
    });
    attachNavListener(document.getElementById('calendar-today'), () => {
        calendar.today();
        setTimeout(() => updateWeekNumberDisplay(), 50);
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
            updateTimezoneSelector();
            applySharedCalendarOptions();
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
        if (eventOverlapObserver) {
            eventOverlapObserver.disconnect();
            eventOverlapObserver = null;
        }

        const chains = await loadChains();
        const expandedChains = getExpandedChains(chains);
        
        calendar = new FullCalendar.Calendar(calendarEl, buildMainCalendarOptions(expandedChains, firstDay, timezone));

        monthCalendar = new FullCalendar.Calendar(monthCalendarEl, buildMonthCalendarOptions(expandedChains, firstDay, timezone));

        calendar.render();
        monthCalendar.render();
        setupEventOverlapObserver(calendarEl);
        
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
    const closeBtn = modal.querySelector('.chains-modal-close');
    const saveBtn = document.getElementById('save-chain-btn');
    const deleteBtn = document.getElementById('delete-chain-btn');
    const addStepBtn = document.getElementById('add-step-btn');
    const stepsContainer = document.getElementById('steps-container');
    const repeatSelect = document.getElementById('chain-repeat');

    closeBtn.addEventListener('click', closeChainEditModal);
    saveBtn.addEventListener('click', saveChain);
    deleteBtn.addEventListener('click', deleteChain);
    repeatSelect.addEventListener('change', toggleRepeatUntilVisibility);
    repeatSelect.addEventListener('input', toggleRepeatUntilVisibility);
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
        const chainsCloseBtn = chainsModal?.querySelector('.chains-modal-close');
        if (!chainsModal || !chainsCloseBtn) return;

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
        
        onTimezoneChange(async (context) => {
            refreshChainModalDateTimes(context);
            await updateCalendarTimezone();
        });

        chainsCloseBtn.addEventListener('click', () => {
            closeChainsModal();
        });

        chainsModal.addEventListener('click', (e) => {
            if (e.target === chainsModal) {
                closeChainsModal();
            }
        });

        document.addEventListener('keydown', (e) => {
            const chainModal = document.getElementById('chain-modal');
            if (chainModal && chainModal.classList.contains('visible')) {
                return;
            }
            if (e.key === 'Escape' && chainsModal.classList.contains('visible')) {
                closeChainsModal();
            }
        });

        setupChainEditModalListeners();
        onAuthChange((authenticated) => {
            if (authenticated) {
                mountFooterToggle();
            } else {
                unmountFooterToggle();
            }
        });
        if (getIsAuthenticated()) {
            mountFooterToggle();
        }
        this.initialized = true;
    }
};
