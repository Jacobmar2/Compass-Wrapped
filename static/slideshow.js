(function () {
  const data = window.slideshowData || {};
  const allSteps = Array.isArray(data.steps) ? [...data.steps].reverse() : [];
  let steps = [...allSteps];

  const mapEl = document.getElementById('slideshowMap');
  const sliderEl = document.getElementById('slideshowSlider');
  const prevEl = document.getElementById('slideshowPrev');
  const nextEl = document.getElementById('slideshowNext');
  const modeOverallEl = document.getElementById('modeOverall');
  const modeTapEl = document.getElementById('modeTap');
  const themeAutoEl = document.getElementById('themeAuto');
  const themeLightOnlyEl = document.getElementById('themeLightOnly');
  const calendarPrevMonthEl = document.getElementById('calendarPrevMonth');
  const calendarNextMonthEl = document.getElementById('calendarNextMonth');
  const calendarMonthLabelEl = document.getElementById('calendarMonthLabel');
  const calendarGridEl = document.getElementById('calendarGrid');
  const calendarClearFilterEl = document.getElementById('calendarClearFilter');
  const calendarCustomRangeEl = document.getElementById('calendarCustomRange');
  const calendarRangeStatusEl = document.getElementById('calendarRangeStatus');
  const metaEl = document.getElementById('slideshowMeta');
  const actionEl = document.getElementById('slideshowAction');
  const sinceEl = document.getElementById('slideshowSince');
  const warningEl = document.getElementById('slideshowWarning');

  if (!allSteps.length || !mapEl || !sliderEl || !prevEl || !nextEl || !window.L) {
    return;
  }

  const map = L.map(mapEl, {
    scrollWheelZoom: true,
  });

  const lightTileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  });

  const darkTileLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
    subdomains: 'abcd',
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO'
  });

  let activeTileTheme = 'light';
  lightTileLayer.addTo(map);

  const pathLayer = L.layerGroup().addTo(map);
  const historyLayer = L.layerGroup().addTo(map);
  let currentMarker = null;
  let playbackMode = 'overall';
  let themeMode = 'auto';
  let currentIndex = 0;
  let selectedDayKey = null;
  let rangeMode = 'none';
  let rangeStartDayKey = null;
  let rangeEndDayKey = null;
  let rangeJumpDayKey = null;
  let calendarMonthCursor = null;
  let lastNavActionAtMs = 0;
  const navDebounceMs = 100;
  const defaultLat = 49.2827;
  const defaultLon = -123.1207;

  const colorByType = {
    station: '#3dd3ff',
    bus: '#fed200',
    wce: '#d131d1',
    seabus: '#B1A59E',
  };

  function markerColor(type) {
    return colorByType[type] || '#3dd3ff';
  }

  function stepDisplayName(step) {
    if (step && step.name) {
      return String(step.name);
    }

    const action = step && step.action ? String(step.action) : '';
    if (action.includes(' at ')) {
      return action.split(' at ', 2)[1];
    }
    return action || 'Stop';
  }

  function placeKeyFromStep(step) {
    return stepDisplayName(step).trim().toLowerCase();
  }

  function createCurrentIcon(stepNumber, markerType) {
    return L.divIcon({
      className: '',
      html: '<div class="ranked-map-marker ' + markerType + '"><span>' + String(stepNumber) + '</span></div>',
      iconSize: [32, 32],
      iconAnchor: [16, 16],
      popupAnchor: [0, -16]
    });
  }

  function buildFoundSteps(untilIndex) {
    const found = [];
    for (let i = 0; i <= untilIndex; i += 1) {
      const step = steps[i];
      if (!step || !step.found) continue;
      found.push({ ...step, stepNumber: i + 1 });
    }
    return found;
  }

  function updateWarning(step) {
    if (!step.warning) {
      warningEl.textContent = '';
      warningEl.classList.add('hidden');
      return;
    }

    warningEl.textContent = step.warning;
    warningEl.classList.remove('hidden');
  }

  function hasAdjacentHighlightedDay(direction) {
    if (rangeMode === 'active') return false;

    const baseDayKey = selectedDayKey || getCurrentVisibleDayKey();
    if (!baseDayKey) return false;

    const currentDayIndex = availableDayKeys.indexOf(baseDayKey);
    if (currentDayIndex < 0) return false;

    const targetDayIndex = currentDayIndex + direction;
    return targetDayIndex >= 0 && targetDayIndex < availableDayKeys.length;
  }

  function updateButtons(index) {
    if (!steps.length) {
      prevEl.disabled = true;
      nextEl.disabled = true;
      return;
    }

    const atStart = index <= 0;
    const atEnd = index >= steps.length - 1;

    prevEl.disabled = atStart && !hasAdjacentHighlightedDay(-1);
    nextEl.disabled = atEnd && !hasAdjacentHighlightedDay(1);
  }

  function canProcessNavAction() {
    const now = Date.now();
    if (now - lastNavActionAtMs < navDebounceMs) {
      return false;
    }
    lastNavActionAtMs = now;
    return true;
  }

  function updateSliderSingleTapState() {
    sliderEl.classList.toggle('single-tap', steps.length === 1);
  }

  function parseCompassTimestamp(text) {
    const value = String(text || '').trim();
    const match = value.match(/^([A-Za-z]{3})-(\d{1,2})-(\d{4})\s+(\d{1,2}):(\d{2})\s+(AM|PM)$/i);
    if (!match) return null;

    const monthMap = {
      Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5,
      Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11,
    };

    const month = monthMap[match[1].slice(0, 1).toUpperCase() + match[1].slice(1, 3).toLowerCase()];
    if (month === undefined) return null;

    const day = Number(match[2]);
    const year = Number(match[3]);
    let hour = Number(match[4]);
    const minute = Number(match[5]);
    const period = match[6].toUpperCase();

    if (period === 'AM' && hour === 12) hour = 0;
    if (period === 'PM' && hour !== 12) hour += 12;

    return new Date(year, month, day, hour, minute, 0, 0);
  }

  function formatDayKey(dateObj) {
    const year = dateObj.getFullYear();
    const month = String(dateObj.getMonth() + 1).padStart(2, '0');
    const day = String(dateObj.getDate()).padStart(2, '0');
    return String(year) + '-' + month + '-' + day;
  }

  function formatDayKeyDisplay(dayKey) {
    const parts = String(dayKey || '').split('-');
    if (parts.length !== 3) return '';

    const year = Number(parts[0]);
    const month = Number(parts[1]);
    const day = Number(parts[2]);
    if (Number.isNaN(year) || Number.isNaN(month) || Number.isNaN(day)) return '';

    const dateObj = new Date(year, month - 1, day);
    const monthShort = dateObj.toLocaleDateString(undefined, { month: 'short' });
    return monthShort + '-' + String(day).padStart(2, '0') + '-' + String(year);
  }

  function resetRangeSelection() {
    rangeMode = 'none';
    rangeStartDayKey = null;
    rangeEndDayKey = null;
    rangeJumpDayKey = null;
  }

  function normalizeRangeBounds() {
    if (!rangeStartDayKey || !rangeEndDayKey) return;
    if (rangeEndDayKey < rangeStartDayKey) {
      const temp = rangeStartDayKey;
      rangeStartDayKey = rangeEndDayKey;
      rangeEndDayKey = temp;
    }
  }

  function isDayWithinRange(dayKey) {
    if (!dayKey || !rangeStartDayKey || !rangeEndDayKey) return false;
    return dayKey >= rangeStartDayKey && dayKey <= rangeEndDayKey;
  }

  function updateRangeUi() {
    if (calendarCustomRangeEl) {
      if (rangeMode === 'await-start') {
        calendarCustomRangeEl.textContent = 'Select Start Date';
      } else if (rangeMode === 'await-end') {
        calendarCustomRangeEl.textContent = 'Select End Date';
      } else if (rangeMode === 'active') {
        calendarCustomRangeEl.textContent = 'Change Custom Range';
      } else {
        calendarCustomRangeEl.textContent = 'Show Custom Range';
      }
    }

    if (calendarRangeStatusEl) {
      if (rangeMode === 'active' && rangeStartDayKey && rangeEndDayKey) {
        const fromText = formatDayKeyDisplay(rangeStartDayKey) || rangeStartDayKey;
        const toText = formatDayKeyDisplay(rangeEndDayKey) || rangeEndDayKey;
        if (rangeJumpDayKey) {
          const jumpText = formatDayKeyDisplay(rangeJumpDayKey) || rangeJumpDayKey;
          calendarRangeStatusEl.textContent = 'Range: ' + fromText + ' to ' + toText + '. Tap ' + jumpText + ' again to filter that day only.';
        } else {
          calendarRangeStatusEl.textContent = 'Range: ' + fromText + ' to ' + toText;
        }
      } else if (rangeMode === 'await-start') {
        calendarRangeStatusEl.textContent = 'Pick the start day from the calendar.';
      } else if (rangeMode === 'await-end' && rangeStartDayKey) {
        const fromText = formatDayKeyDisplay(rangeStartDayKey) || rangeStartDayKey;
        calendarRangeStatusEl.textContent = 'Start: ' + fromText + '. Pick the end day.';
      } else {
        calendarRangeStatusEl.textContent = '';
      }
    }
  }

  function dayKeyFromStep(step) {
    const dateObj = parseCompassTimestamp(step && step.timestamp);
    if (!dateObj) return '';
    return formatDayKey(dateObj);
  }

  const dayToStepsMap = new Map();
  allSteps.forEach(function (step) {
    const key = dayKeyFromStep(step);
    if (!key) return;
    if (!dayToStepsMap.has(key)) {
      dayToStepsMap.set(key, []);
    }
    dayToStepsMap.get(key).push(step);
  });

  const availableDayKeys = Array.from(dayToStepsMap.keys()).sort();
  const availableDaySet = new Set(availableDayKeys);

  function monthKeyToLabel(year, monthIndex) {
    const dateObj = new Date(year, monthIndex, 1);
    return dateObj.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  }

  function getCurrentVisibleDayKey() {
    if (!steps.length) return '';
    return dayKeyFromStep(steps[currentIndex]);
  }

  function setCalendarMonthFromDayKey(dayKey) {
    if (!dayKey) return;
    const parts = dayKey.split('-').map(function (part) { return Number(part); });
    if (parts.length !== 3 || Number.isNaN(parts[0]) || Number.isNaN(parts[1])) return;
    calendarMonthCursor = new Date(parts[0], parts[1] - 1, 1);
  }

  function syncCalendarWithCurrentStep() {
    if (selectedDayKey || !steps.length) return;
    const dayKey = getCurrentVisibleDayKey();
    if (!dayKey) return;

    const parts = dayKey.split('-').map(function (part) { return Number(part); });
    if (parts.length !== 3 || Number.isNaN(parts[0]) || Number.isNaN(parts[1])) return;

    const targetYear = parts[0];
    const targetMonth = parts[1] - 1;
    if (!calendarMonthCursor || calendarMonthCursor.getFullYear() !== targetYear || calendarMonthCursor.getMonth() !== targetMonth) {
      calendarMonthCursor = new Date(targetYear, targetMonth, 1);
    }
    renderCalendar();
  }

  function renderCalendar() {
    if (!calendarGridEl || !calendarMonthLabelEl) return;

    if (!calendarMonthCursor) {
      const fallback = parseCompassTimestamp(allSteps[0] && allSteps[0].timestamp) || new Date();
      calendarMonthCursor = new Date(fallback.getFullYear(), fallback.getMonth(), 1);
    }

    const year = calendarMonthCursor.getFullYear();
    const monthIndex = calendarMonthCursor.getMonth();
    const firstDay = new Date(year, monthIndex, 1);
    const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
    const leadingBlanks = firstDay.getDay();

    calendarMonthLabelEl.textContent = monthKeyToLabel(year, monthIndex);
    calendarGridEl.innerHTML = '';

    for (let i = 0; i < leadingBlanks; i += 1) {
      const blank = document.createElement('span');
      blank.className = 'slideshow-calendar-day empty';
      calendarGridEl.appendChild(blank);
    }

    for (let day = 1; day <= daysInMonth; day += 1) {
      const key = formatDayKey(new Date(year, monthIndex, day));
      const hasData = availableDaySet.has(key);

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'slideshow-calendar-day';
      btn.textContent = String(day);
        
        btn.addEventListener('click', function () {
          if (rangeMode === 'await-start') {
            rangeStartDayKey = key;
            rangeEndDayKey = null;
            rangeMode = 'await-end';
            selectedDayKey = null;
            updateRangeUi();
            renderCalendar();
            return;
          }
          
          if (rangeMode === 'await-end') {
            rangeEndDayKey = key;
            normalizeRangeBounds();
            rangeMode = 'active';
            rangeJumpDayKey = null;
            selectedDayKey = null;
            setCalendarMonthFromDayKey(rangeStartDayKey);
            applyDayFilter();
            updateRangeUi();
            renderCalendar();
            return;
          }
          
          if (rangeMode === 'active') {
            if (isDayWithinRange(key)) {
              if (rangeJumpDayKey && rangeJumpDayKey === key) {
                selectedDayKey = key;
                resetRangeSelection();
                applyDayFilter();
                updateRangeUi();
                renderCalendar();
                return;
              }

              rangeJumpDayKey = key;
              const jumpIndex = steps.findIndex(function (step) {
                return dayKeyFromStep(step) === key;
              });
              if (jumpIndex >= 0) {
                setIndex(jumpIndex);
              }
              updateRangeUi();
              renderCalendar();
              return;
            }

            // If outside active range, fall back to normal single-day selection.
            selectedDayKey = key;
            resetRangeSelection();
            applyDayFilter();
            updateRangeUi();
            renderCalendar();
            return;
          }
          
          selectedDayKey = key;
          applyDayFilter();
          renderCalendar();
        });

      if (hasData) {
        btn.classList.add('has-data');
        btn.title = 'Filter to ' + key;
      } else {
          btn.title = 'Filter to ' + key;
      }

      if (rangeMode === 'active' && isDayWithinRange(key)) {
        btn.classList.add('in-range');
      }

      const activeDayKey = selectedDayKey || ((rangeMode === 'none') ? getCurrentVisibleDayKey() : '');
      if (activeDayKey && activeDayKey === key) {
        btn.classList.add('selected');
      }

      if (rangeMode === 'active' && (key === rangeStartDayKey || key === rangeEndDayKey)) {
        btn.classList.add('selected');
      }

      if (rangeMode === 'await-end' && key === rangeStartDayKey) {
        btn.classList.add('selected');
      }

      if (rangeMode === 'active' && key === getCurrentVisibleDayKey()) {
        btn.classList.add('current-step-day');
      }

      calendarGridEl.appendChild(btn);
    }
  }

  function applyDayFilter() {
    if (rangeMode === 'active' && rangeStartDayKey && rangeEndDayKey) {
      steps = allSteps.filter(function (step) {
        const key = dayKeyFromStep(step);
        return isDayWithinRange(key);
      });
    } else if (!selectedDayKey) {
      steps = [...allSteps];
    } else {
      const selected = dayToStepsMap.get(selectedDayKey);
      steps = selected ? [...selected] : [];
      setCalendarMonthFromDayKey(selectedDayKey);
    }

    sliderEl.max = String(Math.max(steps.length - 1, 0));
    currentIndex = 0;
    updateSliderSingleTapState();

    if (!steps.length) {
      metaEl.textContent = 'No taps for selected day';
      actionEl.textContent = '';
      if (sinceEl) sinceEl.textContent = '';
      warningEl.textContent = '';
      warningEl.classList.add('hidden');
      prevEl.disabled = true;
      nextEl.disabled = true;
      return;
    }

    setIndex(0);
  }

  function jumpToAdjacentHighlightedDay(direction) {
    const baseDayKey = selectedDayKey || getCurrentVisibleDayKey();
    if (!baseDayKey) return false;

    const currentDayIndex = availableDayKeys.indexOf(baseDayKey);
    if (currentDayIndex < 0) return false;

    const targetDayIndex = currentDayIndex + direction;
    if (targetDayIndex < 0 || targetDayIndex >= availableDayKeys.length) return false;

    const targetDayKey = availableDayKeys[targetDayIndex];
    if (!targetDayKey) return false;

    if (selectedDayKey) {
      selectedDayKey = targetDayKey;
      applyDayFilter();
      if (steps.length) {
        if (direction < 0) {
          setIndex(steps.length - 1);
        } else {
          setIndex(0);
        }
      }
      renderCalendar();
      return true;
    }

    const targetSteps = dayToStepsMap.get(targetDayKey);
    if (!targetSteps || !targetSteps.length) return false;

    const targetStep = direction > 0 ? targetSteps[0] : targetSteps[targetSteps.length - 1];
    const targetIndex = allSteps.indexOf(targetStep);
    if (targetIndex < 0) return false;

    setIndex(targetIndex);
    return true;
  }

  function formatSinceText(index) {
    if (index <= 0) return 'Time since last tap: 0 minutes';

    const currentDate = parseCompassTimestamp(steps[index] && steps[index].timestamp);
    const previousDate = parseCompassTimestamp(steps[index - 1] && steps[index - 1].timestamp);
    if (!currentDate || !previousDate || Number.isNaN(currentDate.getTime()) || Number.isNaN(previousDate.getTime())) {
      return 'Time since last tap: Unknown';
    }

    const diffMs = Math.abs(currentDate.getTime() - previousDate.getTime());
    const totalMinutes = Math.floor(diffMs / 60000);
    const days = Math.floor(totalMinutes / 1440);
    const hours = Math.floor((totalMinutes % 1440) / 60);
    const minutes = totalMinutes % 60;

    if (days > 0) {
      return 'Time since last tap: ' + String(days) + ' days, ' + String(hours) + ' hours, ' + String(minutes) + ' minutes';
    }
    if (hours > 0) {
      return 'Time since last tap: ' + String(hours) + ' hours, ' + String(minutes) + ' minutes';
    }
    return 'Time since last tap: ' + String(minutes) + ' minutes';
  }

  // Sun-time math adapted from common astronomical approximations used by SunCalc.
  function solarSunTimes(date, lat, lon) {
    const rad = Math.PI / 180;
    const dayMs = 86400000;
    const J1970 = 2440588;
    const J2000 = 2451545;
    const e = rad * 23.4397;

    function toJulian(dateObj) {
      return dateObj.valueOf() / dayMs - 0.5 + J1970;
    }

    function fromJulian(julian) {
      return new Date((julian + 0.5 - J1970) * dayMs);
    }

    function toDays(dateObj) {
      return toJulian(dateObj) - J2000;
    }

    function rightAscension(l, b) {
      return Math.atan2(Math.sin(l) * Math.cos(e) - Math.tan(b) * Math.sin(e), Math.cos(l));
    }

    function declination(l, b) {
      return Math.asin(Math.sin(b) * Math.cos(e) + Math.cos(b) * Math.sin(e) * Math.sin(l));
    }

    function solarMeanAnomaly(d) {
      return rad * (357.5291 + 0.98560028 * d);
    }

    function eclipticLongitude(m) {
      const c = rad * (1.9148 * Math.sin(m) + 0.02 * Math.sin(2 * m) + 0.0003 * Math.sin(3 * m));
      const p = rad * 102.9372;
      return m + c + p + Math.PI;
    }

    function julianCycle(d, lw) {
      return Math.round(d - 0.0009 - lw / (2 * Math.PI));
    }

    function approxTransit(ht, lw, n) {
      return 0.0009 + (ht + lw) / (2 * Math.PI) + n;
    }

    function solarTransitJ(ds, m, l) {
      return J2000 + ds + 0.0053 * Math.sin(m) - 0.0069 * Math.sin(2 * l);
    }

    function hourAngle(h, phi, dec) {
      return Math.acos((Math.sin(h) - Math.sin(phi) * Math.sin(dec)) / (Math.cos(phi) * Math.cos(dec)));
    }

    function observerAngle(height) {
      return -2.076 * Math.sqrt(height) / 60;
    }

    function getSetJ(h, lw, phi, dec, n, m, l) {
      const w = hourAngle(h, phi, dec);
      const a = approxTransit(w, lw, n);
      return solarTransitJ(a, m, l);
    }

    const lw = rad * -lon;
    const phi = rad * lat;
    const d = toDays(date);

    const n = julianCycle(d, lw);
    const ds = approxTransit(0, lw, n);

    const m = solarMeanAnomaly(ds);
    const l = eclipticLongitude(m);
    const dec = declination(l, 0);

    const jNoon = solarTransitJ(ds, m, l);
    const h0 = (observerAngle(0) - 0.833) * rad;
    const jSet = getSetJ(h0, lw, phi, dec, n, m, l);
    const jRise = jNoon - (jSet - jNoon);

    return {
      sunrise: fromJulian(jRise),
      sunset: fromJulian(jSet),
    };
  }

  function applyMapTheme(theme) {
    if (theme === activeTileTheme) return;

    if (theme === 'dark') {
      if (map.hasLayer(lightTileLayer)) map.removeLayer(lightTileLayer);
      if (!map.hasLayer(darkTileLayer)) darkTileLayer.addTo(map);
      activeTileTheme = 'dark';
      return;
    }

    if (map.hasLayer(darkTileLayer)) map.removeLayer(darkTileLayer);
    if (!map.hasLayer(lightTileLayer)) lightTileLayer.addTo(map);
    activeTileTheme = 'light';
  }

  function updateThemeForStep(currentStep, activeFoundStep) {
    if (themeMode === 'light-only') {
      applyMapTheme('light');
      return;
    }

    const currentDate = parseCompassTimestamp(currentStep && currentStep.timestamp);
    if (!currentDate || Number.isNaN(currentDate.getTime())) {
      applyMapTheme('light');
      return;
    }

    const lat = activeFoundStep && Number.isFinite(activeFoundStep.lat) ? Number(activeFoundStep.lat) : defaultLat;
    const lon = activeFoundStep && Number.isFinite(activeFoundStep.lon) ? Number(activeFoundStep.lon) : defaultLon;

    const sunTimes = solarSunTimes(currentDate, lat, lon);
    if (!sunTimes || !sunTimes.sunrise || !sunTimes.sunset) {
      applyMapTheme('light');
      return;
    }

    const isNight = currentDate.getTime() < sunTimes.sunrise.getTime() || currentDate.getTime() > sunTimes.sunset.getTime();
    applyMapTheme(isNight ? 'dark' : 'light');
  }

  function updateThemeButtons() {
    if (themeAutoEl) {
      themeAutoEl.classList.toggle('active', themeMode === 'auto');
    }
    if (themeLightOnlyEl) {
      themeLightOnlyEl.classList.toggle('active', themeMode === 'light-only');
    }
  }

  function updateModeButtons() {
    if (modeOverallEl) {
      modeOverallEl.classList.toggle('active', playbackMode === 'overall');
    }
    if (modeTapEl) {
      modeTapEl.classList.toggle('active', playbackMode === 'tap');
    }
  }

  function updateMap(index) {
    if (!steps.length) return;

    const currentStep = steps[index];
    const foundSteps = buildFoundSteps(index);
    const cumulativeUsesByPlace = new Map();

    foundSteps.forEach(function (step) {
      const key = placeKeyFromStep(step);
      cumulativeUsesByPlace.set(key, (cumulativeUsesByPlace.get(key) || 0) + 1);
    });

    pathLayer.clearLayers();
    historyLayer.clearLayers();

    if (currentMarker) {
      map.removeLayer(currentMarker);
      currentMarker = null;
    }

    if (playbackMode === 'overall') {
      for (let i = 1; i < foundSteps.length; i += 1) {
        const prev = foundSteps[i - 1];
        const curr = foundSteps[i];
        L.polyline(
          [
            [prev.lat, prev.lon],
            [curr.lat, curr.lon]
          ],
          {
            color: markerColor(curr.marker_type),
            weight: 4,
            opacity: 0.8
          }
        ).addTo(pathLayer);
      }

      for (let i = 0; i < foundSteps.length - 1; i += 1) {
        const step = foundSteps[i];
        const displayName = stepDisplayName(step);
        const uses = cumulativeUsesByPlace.get(placeKeyFromStep(step)) || 0;
        const popupText = playbackMode === 'overall'
          ? (displayName + '<br>Total uses so far: ' + String(uses))
          : displayName;
        L.circleMarker([step.lat, step.lon], {
          radius: 5,
          color: '#ffffff',
          weight: 2,
          fillColor: markerColor(step.marker_type),
          fillOpacity: 0.9,
        })
          .addTo(historyLayer)
          .bindPopup(popupText);
      }
    }

    const activeFoundStep = foundSteps.length ? foundSteps[foundSteps.length - 1] : null;
    updateThemeForStep(currentStep, activeFoundStep);

    if (activeFoundStep) {
      const activeDisplayName = stepDisplayName(activeFoundStep);
      const activeUses = cumulativeUsesByPlace.get(placeKeyFromStep(activeFoundStep)) || 0;
      const activePopupText = playbackMode === 'overall'
        ? (activeDisplayName + '<br>Total uses so far: ' + String(activeUses))
        : activeDisplayName;
      currentMarker = L.marker([activeFoundStep.lat, activeFoundStep.lon], {
        icon: createCurrentIcon(activeFoundStep.stepNumber, activeFoundStep.marker_type),
        zIndexOffset: 25000,
      })
        .addTo(map)
        .bindPopup(activePopupText);

      if (playbackMode === 'tap') {
        map.setView(L.latLng(activeFoundStep.lat, activeFoundStep.lon), 15);
      } else {
        const latLngs = foundSteps.map((step) => L.latLng(step.lat, step.lon));
        if (latLngs.length === 1) {
          map.setView(latLngs[0], 13);
        } else {
          map.fitBounds(latLngs, { padding: [36, 36] });
        }
      }
    }

    const baseMeta = 'Tap ' + String(index + 1) + ' of ' + String(steps.length);
    if (selectedDayKey) {
      const displayDay = formatDayKeyDisplay(selectedDayKey);
      metaEl.textContent = displayDay ? (displayDay + ': ' + baseMeta) : baseMeta;
    } else {
      metaEl.textContent = baseMeta;
    }

    let stepLabel = currentStep.action || '';
    if (currentStep.name) {
      stepLabel += ' [' + currentStep.name + ']';
    }
    const timestamp = currentStep.timestamp ? (' (' + currentStep.timestamp + ')') : '';
    actionEl.textContent = stepLabel + timestamp;
    if (sinceEl) {
      sinceEl.textContent = formatSinceText(index);
    }

    updateWarning(currentStep);
    updateButtons(index);
  }

  function setIndex(index) {
    if (!steps.length) return;

    const bounded = Math.max(0, Math.min(index, steps.length - 1));
    currentIndex = bounded;
    sliderEl.value = String(bounded);
    updateMap(bounded);
    syncCalendarWithCurrentStep();
  }

  sliderEl.addEventListener('input', function () {
    setIndex(Number(sliderEl.value));
  });

  prevEl.addEventListener('click', function () {
    if (!canProcessNavAction()) return;
    if (!steps.length) return;

    const index = Number(sliderEl.value);
    if (index <= 0) {
      jumpToAdjacentHighlightedDay(-1);
      return;
    }
    setIndex(index - 1);
  });

  nextEl.addEventListener('click', function () {
    if (!canProcessNavAction()) return;
    if (!steps.length) return;

    const index = Number(sliderEl.value);
    if (index >= steps.length - 1) {
      jumpToAdjacentHighlightedDay(1);
      return;
    }
    setIndex(index + 1);
  });

  if (modeOverallEl) {
    modeOverallEl.addEventListener('click', function () {
      playbackMode = 'overall';
      updateModeButtons();
      updateMap(currentIndex);
    });
  }

  if (modeTapEl) {
    modeTapEl.addEventListener('click', function () {
      playbackMode = 'tap';
      updateModeButtons();
      updateMap(currentIndex);
    });
  }

  if (themeAutoEl) {
    themeAutoEl.addEventListener('click', function () {
      themeMode = 'auto';
      updateThemeButtons();
      updateMap(currentIndex);
    });
  }

  if (themeLightOnlyEl) {
    themeLightOnlyEl.addEventListener('click', function () {
      themeMode = 'light-only';
      updateThemeButtons();
      updateMap(currentIndex);
    });
  }

  if (calendarPrevMonthEl) {
    calendarPrevMonthEl.addEventListener('click', function () {
      if (!calendarMonthCursor) return;
      calendarMonthCursor = new Date(calendarMonthCursor.getFullYear(), calendarMonthCursor.getMonth() - 1, 1);
      renderCalendar();
    });
  }

  if (calendarNextMonthEl) {
    calendarNextMonthEl.addEventListener('click', function () {
      if (!calendarMonthCursor) return;
      calendarMonthCursor = new Date(calendarMonthCursor.getFullYear(), calendarMonthCursor.getMonth() + 1, 1);
      renderCalendar();
    });
  }

  if (calendarClearFilterEl) {
    calendarClearFilterEl.addEventListener('click', function () {
      selectedDayKey = null;
      resetRangeSelection();
      applyDayFilter();
      syncCalendarWithCurrentStep();
      updateRangeUi();
      renderCalendar();
    });
  }

  if (calendarCustomRangeEl) {
    calendarCustomRangeEl.addEventListener('click', function () {
      selectedDayKey = null;
      rangeStartDayKey = null;
      rangeEndDayKey = null;
      rangeJumpDayKey = null;
      rangeMode = 'await-start';
      updateRangeUi();
      renderCalendar();
    });
  }

  requestAnimationFrame(function () {
    map.invalidateSize();
    updateModeButtons();
    updateThemeButtons();
    if (availableDayKeys.length) {
      const first = availableDayKeys[0].split('-').map(function (part) { return Number(part); });
      calendarMonthCursor = new Date(first[0], first[1] - 1, 1);
    }
    updateRangeUi();
    renderCalendar();
    applyDayFilter();
  });

  window.addEventListener('resize', function () {
    requestAnimationFrame(function () {
      map.invalidateSize();
      updateMap(currentIndex);
    });
  });
})();
