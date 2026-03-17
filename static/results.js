document.addEventListener('DOMContentLoaded', () => {
  const data = window.resultsData || {};

  // Helper: safe get element
  const $ = (id) => document.getElementById(id);

  // ========== DEEPER STATS TOGGLE ==========
  const topStationPairsSection = $('topStationPairsSection');
  const dayHourCarouselContainer = $('dayHourCarouselContainer');
  const deeperStatsToggle = $('deeperStatsToggle');
  const dayHourCharts = [];
  let deeperStatsVisible = false;

  function refreshDayHourStatsLayout() {
    if (!deeperStatsVisible) return;

    requestAnimationFrame(() => {
      if (typeof goToDayHourSlide === 'function') {
        goToDayHourSlide(currentDayHourSlide);
      }
      if (typeof updateDayHourCarouselHeight === 'function') {
        updateDayHourCarouselHeight();
      }
      dayHourCharts.forEach((chart) => {
        chart.resize();
        chart.update('none');
      });
    });

    setTimeout(() => {
      if (typeof goToDayHourSlide === 'function') {
        goToDayHourSlide(currentDayHourSlide);
      }
      dayHourCharts.forEach((chart) => {
        chart.resize();
      });
    }, 80);
  }

  function setDeeperStatsVisibility(isVisible) {
    deeperStatsVisible = isVisible;
    const displayValue = isVisible ? '' : 'none';

    if (topStationPairsSection) topStationPairsSection.style.display = displayValue;
    if (dayHourCarouselContainer) dayHourCarouselContainer.style.display = displayValue;
    if (deeperStatsToggle) deeperStatsToggle.textContent = isVisible ? 'Hide deeper stats' : 'Reveal deeper stats';

    const sidebarDeeperToggle = $('sidebarDeeperToggle');
    const sidebarDeeperMenu = $('sidebarDeeperMenu');
    if (sidebarDeeperToggle) sidebarDeeperToggle.classList.toggle('open', isVisible);
    if (sidebarDeeperMenu) sidebarDeeperMenu.classList.toggle('open', isVisible);

    if (isVisible) refreshDayHourStatsLayout();
  }

  window.toggleDeeperStats = function() {
    setDeeperStatsVisibility(!deeperStatsVisible);
  };

  window.setDeeperStatsVisibility = setDeeperStatsVisibility;

  setDeeperStatsVisibility(false);

  // ========== END DEEPER STATS TOGGLE ==========

  // ========== LEFT SIDEBAR ==========
  const resultsSidebar = $('resultsSidebar');
  const sidebarToggle = $('sidebarToggle');
  const sidebarDeeperToggle = $('sidebarDeeperToggle');
  const sidebarLinks = Array.from(document.querySelectorAll('.sidebar-link[data-section]'));

  if (sidebarToggle && resultsSidebar) {
    sidebarToggle.addEventListener('click', () => {
      resultsSidebar.classList.toggle('collapsed');
    });
  }

  if (sidebarDeeperToggle) {
    sidebarDeeperToggle.addEventListener('click', () => {
      setDeeperStatsVisibility(!deeperStatsVisible);
    });
  }

  sidebarLinks.forEach((link) => {
    link.addEventListener('click', (event) => {
      event.preventDefault();

      const targetId = link.getAttribute('data-section');
      const targetElement = targetId ? document.getElementById(targetId) : null;
      const requiresDeeper = link.getAttribute('data-requires-deeper') === 'true';

      if (requiresDeeper && !deeperStatsVisible) {
        setDeeperStatsVisibility(true);
      }

      if (!targetElement) return;

      targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (history.replaceState) {
        history.replaceState(null, '', `#${targetId}`);
      }
    });
  });

  function updateActiveSidebarSection() {
    if (!sidebarLinks.length) return;

    const viewportAnchor = Math.max(140, Math.round(window.innerHeight * 0.25));
    let activeId = null;
    let bestDistance = Number.POSITIVE_INFINITY;

    sidebarLinks.forEach((link) => {
      const sectionId = link.getAttribute('data-section');
      const section = sectionId ? document.getElementById(sectionId) : null;
      if (!section || section.offsetParent === null) return;

      const rect = section.getBoundingClientRect();
      const isInViewBand = rect.top <= viewportAnchor && rect.bottom >= viewportAnchor;
      const distance = Math.abs(rect.top - viewportAnchor);

      if (isInViewBand && distance < bestDistance) {
        bestDistance = distance;
        activeId = sectionId;
      }
    });

    if (!activeId) {
      sidebarLinks.forEach((link) => {
        const sectionId = link.getAttribute('data-section');
        const section = sectionId ? document.getElementById(sectionId) : null;
        if (!section || section.offsetParent === null) return;
        const distance = Math.abs(section.getBoundingClientRect().top - viewportAnchor);
        if (distance < bestDistance) {
          bestDistance = distance;
          activeId = sectionId;
        }
      });
    }

    sidebarLinks.forEach((link) => {
      link.classList.toggle('active', link.getAttribute('data-section') === activeId);
    });
  }

  window.addEventListener('scroll', updateActiveSidebarSection, { passive: true });
  window.addEventListener('resize', updateActiveSidebarSection);
  updateActiveSidebarSection();

  // ========== END LEFT SIDEBAR ==========

  // ========== TOP STOPS MAP ==========
  try {
    const mapContainer = $('topStopsMap');
    const stationPoints = Array.isArray(data.top_station_map_points) ? data.top_station_map_points : [];
    const busPoints = Array.isArray(data.top_bus_stop_map_points) ? data.top_bus_stop_map_points : [];
    const remainingStationPoints = Array.isArray(data.remaining_station_map_points) ? data.remaining_station_map_points : [];
    const remainingBusPoints = Array.isArray(data.remaining_bus_stop_map_points) ? data.remaining_bus_stop_map_points : [];
    const initialMapPoints = [
      ...stationPoints.map((point) => ({ ...point, markerType: 'station' })),
      ...busPoints.map((point) => ({ ...point, markerType: 'bus' }))
    ];

    if (mapContainer && initialMapPoints.length && window.L) {
      const map = L.map(mapContainer, {
        scrollWheelZoom: true,
      });
      const strongestZoom = 19;

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
      }).addTo(map);

      const rankedMarkers = [];

      const createRankedIcon = (markerType, rank) => L.divIcon({
        className: '',
        html: `<div class="ranked-map-marker ${markerType}"><span>${rank}</span></div>`,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
        popupAnchor: [0, -16]
      });

      const markerZIndexOffset = (point) => {
        const typeBase = point.markerType === 'station' ? 20000 : 10000;
        return typeBase + (100 - point.rank);
      };

      const updateOverlappingMarkerPositions = () => {
        const zoom = map.getZoom();
        const groups = new Map();

        rankedMarkers.forEach(({ marker, point, originalLatLng }) => {
          marker.setLatLng(originalLatLng);

          const key = `${point.lat.toFixed(6)},${point.lon.toFixed(6)}`;
          if (!groups.has(key)) {
            groups.set(key, []);
          }
          groups.get(key).push({ marker, point, originalLatLng });
        });

        if (zoom < strongestZoom) {
          return;
        }

        groups.forEach((group) => {
          if (group.length < 2) {
            return;
          }

          const orderedGroup = [...group].sort((left, right) => markerZIndexOffset(right.point) - markerZIndexOffset(left.point));
          const spacing = 34;
          const centerIndex = (orderedGroup.length - 1) / 2;
          const basePoint = map.project(orderedGroup[0].originalLatLng, zoom);

          orderedGroup.forEach((entry, index) => {
            const offsetX = (index - centerIndex) * spacing;
            const shiftedLatLng = map.unproject(L.point(basePoint.x + offsetX, basePoint.y), zoom);
            entry.marker.setLatLng(shiftedLatLng);
          });
        });
      };

      const fitDisplayedMarkers = () => {
        const displayedBounds = rankedMarkers.map(({ marker }) => marker.getLatLng());
        if (displayedBounds.length === 1) {
          map.setView(displayedBounds[0], 13);
          return;
        }
        if (displayedBounds.length > 1) {
          map.fitBounds(displayedBounds, { padding: [36, 36] });
        }
      };

      const addPointMarker = (point) => {
        const popupTitle = point.markerType === 'station'
          ? `Station #${point.rank}: ${point.name}`
          : `Bus Stop #${point.rank}: ${point.name}`;

        const popupMeta = point.markerType === 'station'
          ? `Uses: ${point.count}${point.source_name ? `<br>Location source: ${point.source_name}` : ''}`
          : `Stop #${point.stop_id}<br>Uses: ${point.count}`;

        const originalLatLng = L.latLng(point.lat, point.lon);
        const marker = L.marker(originalLatLng, {
          icon: createRankedIcon(point.markerType, point.rank),
          zIndexOffset: markerZIndexOffset(point)
        })
          .addTo(map)
          .bindPopup(
            `<div class="map-popup-title">${popupTitle}</div><div class="map-popup-meta">${popupMeta}</div>`
          );

        rankedMarkers.push({ marker, point, originalLatLng });
      };

      initialMapPoints.forEach(addPointMarker);
      fitDisplayedMarkers();

      requestAnimationFrame(() => {
        map.invalidateSize();
        updateOverlappingMarkerPositions();
      });

      map.on('zoomend', updateOverlappingMarkerPositions);

      const revealMoreStationsButton = $('revealMoreStations');
      if (revealMoreStationsButton && remainingStationPoints.length) {
        let stationRevealIndex = 0;
        const stationRevealChunk = 5;

        const updateStationButtonState = () => {
          const remaining = remainingStationPoints.length - stationRevealIndex;
          if (remaining <= 0) {
            revealMoreStationsButton.disabled = true;
            revealMoreStationsButton.textContent = 'All Stations Revealed';
          } else {
            revealMoreStationsButton.textContent = `Reveal Next ${Math.min(stationRevealChunk, remaining)} Stations`;
          }
        };

        revealMoreStationsButton.addEventListener('click', () => {
          const nextSlice = remainingStationPoints
            .slice(stationRevealIndex, stationRevealIndex + stationRevealChunk)
            .map((point) => ({ ...point, markerType: 'station' }));

          nextSlice
            .forEach(addPointMarker);
          stationRevealIndex += nextSlice.length;

          fitDisplayedMarkers();
          updateOverlappingMarkerPositions();
          updateStationButtonState();
        });

        updateStationButtonState();
      }

      const revealMoreBusStopsButton = $('revealMoreBusStops');
      if (revealMoreBusStopsButton && remainingBusPoints.length) {
        let busRevealIndex = 0;
        const busRevealChunk = 10;

        const updateBusButtonState = () => {
          const remaining = remainingBusPoints.length - busRevealIndex;
          if (remaining <= 0) {
            revealMoreBusStopsButton.disabled = true;
            revealMoreBusStopsButton.textContent = 'All Bus Stops Revealed';
          } else {
            revealMoreBusStopsButton.textContent = `Reveal Next ${Math.min(busRevealChunk, remaining)} Bus Stops`;
          }
        };

        revealMoreBusStopsButton.addEventListener('click', () => {
          const nextSlice = remainingBusPoints
            .slice(busRevealIndex, busRevealIndex + busRevealChunk)
            .map((point) => ({ ...point, markerType: 'bus' }));

          nextSlice
            .forEach(addPointMarker);
          busRevealIndex += nextSlice.length;

          fitDisplayedMarkers();
          updateOverlappingMarkerPositions();
          updateBusButtonState();
        });

        updateBusButtonState();
      }
    }
  } catch (e) { console.error('top stops map error', e); }

  // ========== END TOP STOPS MAP ==========

  // ========== STATION CHART SORTING ==========
  let stationChart = null;
  let currentStationSortMode = 'usage';
  
  window.sortStationChart = function(mode) {
    currentStationSortMode = mode;
    
    // Update button states
    document.getElementById('stationSortUsage')?.classList.toggle('active', mode === 'usage');
    document.getElementById('stationSortAlpha')?.classList.toggle('active', mode === 'alphabetical');
    
    // Get sorted data
    let labels = [...(data.station_labels || [])];
    let values = [...(data.station_values || [])];
    
    // Create array of [label, value] pairs
    let pairs = labels.map((label, idx) => ({ label, value: values[idx] }));
    
    if (mode === 'alphabetical') {
      pairs.sort((a, b) => a.label.localeCompare(b.label));
    } else {
      // Sort by value descending (usage)
      pairs.sort((a, b) => b.value - a.value);
    }
    
    // Extract sorted labels and values
    const sortedLabels = pairs.map(p => p.label);
    const sortedValues = pairs.map(p => p.value);
    
    // Update chart data and re-render
    if (stationChart) {
      stationChart.data.labels = sortedLabels;
      stationChart.data.datasets[0].data = sortedValues;
      stationChart.update();
    }
  };

  // ========== END STATION CHART SORTING ==========

  // -------------------------------
  // Charts (create only if canvas exists)
  // -------------------------------
  try {
    const stationCanvas = $('stationChart');
    if (stationCanvas && data.station_labels && data.station_values) {
      stationChart = new Chart(stationCanvas.getContext('2d'), {
        type: 'bar',
        data: {
          labels: data.station_labels,
          datasets: [{ label: 'Station Usage', data: data.station_values, backgroundColor: '#4da6ff' }]
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          plugins: { tooltip: { enabled: true }, legend: { display: false } },
          scales: { x: { beginAtZero: true }, y: { ticks: { autoSkip: false } } }
        }
      });
    }
  } catch (e) { console.error('station chart error', e); }

  try {
    const hourCanvas = $('hourChart');
    if (hourCanvas && data.hours && data.hour_values) {
      new Chart(hourCanvas.getContext('2d'), {
        type: 'bar',
        data: { labels: data.hours, datasets: [{ label: 'Trips by Hour', data: data.hour_values, backgroundColor: '#4da6ff' }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { tooltip: { enabled: true }, legend: { display: false } }, scales: { y: { beginAtZero: true } } }
      });
    }
  } catch (e) { console.error('hour chart error', e); }

  try {
    const weekdayCanvas = $('weekdayChart');
    if (weekdayCanvas && data.days && data.weekday_values) {
      new Chart(weekdayCanvas.getContext('2d'), {
        type: 'bar',
        data: { labels: data.days, datasets: [{ label: 'Trips by Day', data: data.weekday_values, backgroundColor: '#4da6ff' }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { tooltip: { enabled: true }, legend: { display: false } }, scales: { y: { beginAtZero: true } } }
      });
    }
  } catch (e) { console.error('weekday chart error', e); }

  try {
    const monthCanvas = $('monthChart');
    if (monthCanvas && data.month && data.month_values) {
      new Chart(monthCanvas.getContext('2d'), {
        type: 'bar',
        data: { labels: data.month, datasets: [{ label: 'Trips by Month', data: data.month_values, backgroundColor: '#4da6ff' }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { tooltip: { enabled: true }, legend: { display: false } }, scales: { y: { beginAtZero: true } } }
      });
    }
  } catch (e) { console.error('month chart error', e); }

  try {
    const weekdayNames = data.weekday_full_names || [];
    const dayHourValues = data.day_hour_values || [];
    const hourLabels = data.hours || Array.from({ length: 24 }, (_, i) => i);

    weekdayNames.forEach((dayName, dayIndex) => {
      const canvas = $(`dayHourChart${dayIndex}`);
      const values = Array.isArray(dayHourValues[dayIndex]) ? dayHourValues[dayIndex] : Array(24).fill(0);

      if (!canvas) return;

      const dayHourChart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
          labels: hourLabels,
          datasets: [{ label: `Trips by Hour (${dayName})`, data: values, backgroundColor: '#4da6ff' }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { tooltip: { enabled: true }, legend: { display: false } },
          scales: { y: { beginAtZero: true } }
        }
      });

      dayHourCharts.push(dayHourChart);
    });
  } catch (e) { console.error('weekday-hour chart error', e); }

  // SSW Pie / Breakdown charts
  try {
    const sswCanvas = $('sswPieChart');
    if (sswCanvas && data.ssw_counts) {
      new Chart(sswCanvas.getContext('2d'), {
        type: 'pie',
        data: {
          labels: data.ssw_counts_labels || ['SSW', 'Bus Only'],
          datasets: [{ data: data.ssw_counts, backgroundColor: ['#4da6ff', '#0059b3'] }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
      });
    }
  } catch (e) { console.error('ssw pie chart error', e); }

  try {
    const breakdownCanvas = $('sswBreakdownChart');
    if (breakdownCanvas && data.ssw_breakdown) {
      new Chart(breakdownCanvas.getContext('2d'), {
        type: 'pie',
        data: {
          labels: data.ssw_breakdown_labels || ['SkyTrain', 'SeaBus', 'WCE'],
          datasets: [{ data: data.ssw_breakdown, backgroundColor: ['#009cde', '#B1A59E', '#d131d1'] }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
      });
    }
  } catch (e) { console.error('ssw breakdown chart error', e); }

  // -------------------------------
  // Carousel
  // -------------------------------
  let currentSlide = 0;
  const carousel = document.getElementById('carousel');
  const slides = carousel ? carousel.querySelectorAll('.slide') : [];
  const indicators = document.querySelectorAll('.indicator:not(.day-hour-indicator)');

  function updateCarouselHeight() {
    if (!slides || !slides.length || !carousel) return;
    const activeSlide = slides[currentSlide];
    carousel.style.height = activeSlide.scrollHeight + 'px';
  }

  function goToSlide(index) {
    if (!carousel) return;
    currentSlide = index;
    carousel.style.transform = `translateX(-${index * 100}%)`;

    indicators.forEach((dot, i) => dot.classList.toggle('active', i === index));
    updateCarouselHeight();
  }

  function moveSlide(direction) {
    if (!slides || !slides.length) return;
    let newIndex = currentSlide + direction;
    if (newIndex < 0) newIndex = slides.length - 1;
    if (newIndex >= slides.length) newIndex = 0;
    goToSlide(newIndex);
  }

  // Expose functions (template uses inline onclick)
  window.goToSlide = goToSlide;
  window.moveSlide = moveSlide;

  // Initialize height and listeners
  updateCarouselHeight();
  window.addEventListener('resize', updateCarouselHeight);

  // -------------------------------
  // Day-hour Carousel (second carousel)
  // -------------------------------
  let currentDayHourSlide = 0;
  const dayHourCarousel = document.getElementById('dayHourCarousel');
  const dayHourSlides = dayHourCarousel ? dayHourCarousel.querySelectorAll('.day-hour-slide') : [];
  const dayHourIndicators = document.querySelectorAll('.day-hour-indicator');

  function updateDayHourCarouselHeight() {
    if (!dayHourSlides.length || !dayHourCarousel) return;
    const activeSlide = dayHourSlides[currentDayHourSlide];
    dayHourCarousel.style.height = activeSlide.scrollHeight + 'px';
  }

  function goToDayHourSlide(index) {
    if (!dayHourCarousel) return;
    currentDayHourSlide = index;
    dayHourCarousel.style.transform = `translateX(-${index * 100}%)`;

    dayHourIndicators.forEach((dot, i) => dot.classList.toggle('active', i === index));
    updateDayHourCarouselHeight();
  }

  function moveDayHourSlide(direction) {
    if (!dayHourSlides.length) return;
    let newIndex = currentDayHourSlide + direction;
    if (newIndex < 0) newIndex = dayHourSlides.length - 1;
    if (newIndex >= dayHourSlides.length) newIndex = 0;
    goToDayHourSlide(newIndex);
  }

  window.goToDayHourSlide = goToDayHourSlide;
  window.moveDayHourSlide = moveDayHourSlide;
  updateDayHourCarouselHeight();
  window.addEventListener('resize', updateDayHourCarouselHeight);

  // -------------------------------
  // Awards row carousels
  // -------------------------------
  const awardCarouselState = {};

  function getAwardTrack(index) {
    return document.getElementById(`awardCarouselTrack${index}`);
  }

  function getAwardButton(index, type) {
    return document.getElementById(`award${type}${index}`);
  }

  function getAwardMaxIndex(track) {
    if (!track) return 0;
    const cardCount = track.children.length;
    const cardsPerPage = window.innerWidth <= 700 ? 1 : 2;
    const totalPages = Math.ceil(cardCount / cardsPerPage);
    return Math.max(0, totalPages - 1);
  }

  function updateAwardCarousel(index) {
    const track = getAwardTrack(index);
    if (!track || !track.children.length) return;

    const computedStyles = window.getComputedStyle(track);
    const gap = parseFloat(computedStyles.gap || computedStyles.columnGap || '0') || 0;
    const cardWidth = track.children[0].getBoundingClientRect().width;
    const maxIndex = getAwardMaxIndex(track);
    const cardsPerPage = window.innerWidth <= 700 ? 1 : 2;

    if (!Object.prototype.hasOwnProperty.call(awardCarouselState, index)) {
      awardCarouselState[index] = 0;
    }

    awardCarouselState[index] = Math.max(0, Math.min(awardCarouselState[index], maxIndex));

    const offsetX = awardCarouselState[index] * cardsPerPage * (cardWidth + gap);
    track.style.transform = `translateX(-${offsetX}px)`;

    const prevButton = getAwardButton(index, 'Prev');
    const nextButton = getAwardButton(index, 'Next');
    if (prevButton) prevButton.disabled = awardCarouselState[index] <= 0;
    if (nextButton) nextButton.disabled = awardCarouselState[index] >= maxIndex;
  }

  window.moveAwardSlide = function(index, direction) {
    if (!Object.prototype.hasOwnProperty.call(awardCarouselState, index)) {
      awardCarouselState[index] = 0;
    }
    awardCarouselState[index] += direction;
    updateAwardCarousel(index);
  };

  const awardTracks = document.querySelectorAll('[id^="awardCarouselTrack"]');
  awardTracks.forEach((track) => {
    const index = parseInt(track.id.replace('awardCarouselTrack', ''), 10);
    if (!Number.isNaN(index)) {
      awardCarouselState[index] = 0;
      updateAwardCarousel(index);
    }
  });

  window.addEventListener('resize', () => {
    Object.keys(awardCarouselState).forEach((index) => {
      updateAwardCarousel(Number(index));
    });
  });
});