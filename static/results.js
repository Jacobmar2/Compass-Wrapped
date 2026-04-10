document.addEventListener('DOMContentLoaded', () => {
  const data = window.resultsData || {};

  // Helper: safe get element
  const $ = (id) => document.getElementById(id);
  const isPhoneMode = () => window.matchMedia('(max-width: 768px)').matches;
  const isPhonePortrait = () => isPhoneMode() && window.matchMedia('(orientation: portrait)').matches;
  const isSideView = () => window.matchMedia('(orientation: landscape) and (max-height: 500px)').matches;
  const isSwipeMode = () => isPhoneMode() || isSideView();

  // If another page requested a targeted scroll, perform it now and clear the flag.
  try {
    const requested = sessionStorage.getItem('scrollToSection');
    if (requested) {
      sessionStorage.removeItem('scrollToSection');
      const targetEl = document.getElementById(requested);
      if (targetEl) {
        // Close sidebar overlay if open to avoid landing under it
        const sidebar = document.getElementById('resultsSidebar');
        const overlay = document.getElementById('sidebarOverlay');
        if (sidebar) sidebar.classList.add('collapsed');
        if (overlay) {
          overlay.classList.remove('open');
          overlay.setAttribute('aria-hidden', 'true');
        }
        // Smooth-scroll to the element after a tiny delay to let layout settle
        setTimeout(() => {
          try {
            targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
            // give other scroll handlers a moment to update active state
            setTimeout(() => window.dispatchEvent(new Event('scroll')), 250);
          } catch (err) {
            // ignore
          }
        }, 60);
      }
    }
  } catch (err) {
    // sessionStorage may be unavailable in some contexts
  }

  function formatHourLabel(hourValue, compact = true) {
    const numericHour = Number(hourValue);
    if (Number.isNaN(numericHour)) return String(hourValue);

    const normalizedHour = ((numericHour % 24) + 24) % 24;
    const suffix = normalizedHour < 12 ? 'AM' : 'PM';
    const twelveHour = normalizedHour % 12 === 0 ? 12 : normalizedHour % 12;

    return compact ? `${twelveHour}${suffix === 'AM' ? 'a' : 'p'}` : `${twelveHour}:00 ${suffix}`;
  }

  function getBarChartFontSize() {
    if (window.matchMedia('(max-width: 360px)').matches) return 9;
    if (window.matchMedia('(max-width: 600px)').matches) return 10;
    if (window.matchMedia('(max-width: 768px)').matches) return 11;
    return 12;
  }

  function bindAxisLabelTooltip(chart, { axis = 'x' } = {}) {
    if (!chart || !chart.canvas) return;

    const getPointerPosition = (event) => {
      const point = event.touches && event.touches.length ? event.touches[0] : event;
      const rect = chart.canvas.getBoundingClientRect();
      return {
        x: point.clientX - rect.left,
        y: point.clientY - rect.top,
      };
    };

    const getLabelIndex = (event) => {
      const chartArea = chart.chartArea;
      if (!chartArea) return null;

      const pointer = getPointerPosition(event);
      let rawIndex = null;

      if (axis === 'x' && chart.scales.x) {
        const inXAxisBand = pointer.y >= chartArea.bottom && pointer.y <= chart.height;
        if (!inXAxisBand) return null;
        rawIndex = chart.scales.x.getValueForPixel(pointer.x);
      } else if (axis === 'y' && chart.scales.y) {
        const inYAxisBand = pointer.x >= 0 && pointer.x <= chartArea.left;
        if (!inYAxisBand) return null;
        rawIndex = chart.scales.y.getValueForPixel(pointer.y);
      }

      if (rawIndex === null || Number.isNaN(rawIndex)) return null;

      const dataLength = chart.data?.datasets?.[0]?.data?.length || 0;
      if (!dataLength) return null;

      const index = Math.round(rawIndex);
      if (index < 0 || index >= dataLength) return null;
      return index;
    };

    const showTooltipForIndex = (index) => {
      const element = chart.getDatasetMeta(0)?.data?.[index];
      if (!element) return;

      const active = [{ datasetIndex: 0, index }];
      const position = element.tooltipPosition();
      chart.setActiveElements(active);
      if (chart.tooltip) {
        chart.tooltip.setActiveElements(active, position);
      }
      chart.update('none');
    };

    const clearTooltip = () => {
      chart.setActiveElements([]);
      if (chart.tooltip) {
        chart.tooltip.setActiveElements([], { x: 0, y: 0 });
      }
      chart.update('none');
    };

    chart.canvas.addEventListener('mousemove', (event) => {
      const index = getLabelIndex(event);
      if (index === null) {
        clearTooltip();
        return;
      }
      showTooltipForIndex(index);
    });

    chart.canvas.addEventListener('mouseleave', clearTooltip);

    chart.canvas.addEventListener('click', (event) => {
      const index = getLabelIndex(event);
      if (index !== null) showTooltipForIndex(index);
    });

    chart.canvas.addEventListener('touchstart', (event) => {
      const index = getLabelIndex(event);
      if (index !== null) showTooltipForIndex(index);
    }, { passive: true });
  }

  function bindSwipeCarousel(viewportEl, {
    onSwipeLeft,
    onSwipeRight,
    isEnabled = isPhoneMode,
    ignoreInteractiveTargets = true
  }) {
    if (!viewportEl) return;

    let tracking = false;
    let pointerId = null;
    let startX = 0;
    let startY = 0;
    let deltaX = 0;
    let deltaY = 0;
    let axisLock = null;

    const movementStartThreshold = 10;
    const swipeThreshold = 45;

    const resetState = () => {
      tracking = false;
      pointerId = null;
      startX = 0;
      startY = 0;
      deltaX = 0;
      deltaY = 0;
      axisLock = null;
      viewportEl.classList.remove('is-swiping');
    };

    viewportEl.addEventListener('pointerdown', (event) => {
      if (!isEnabled() || !event.isPrimary) return;
      if (ignoreInteractiveTargets && event.target.closest('button, a, input, select, textarea, label')) return;

      tracking = true;
      pointerId = event.pointerId;
      startX = event.clientX;
      startY = event.clientY;
      deltaX = 0;
      deltaY = 0;
      axisLock = null;
      viewportEl.classList.add('is-swiping');
    }, { passive: true });

    viewportEl.addEventListener('pointermove', (event) => {
      if (!tracking || event.pointerId !== pointerId) return;

      deltaX = event.clientX - startX;
      deltaY = event.clientY - startY;

      if (!axisLock) {
        if (Math.abs(deltaX) < movementStartThreshold && Math.abs(deltaY) < movementStartThreshold) return;
        axisLock = Math.abs(deltaX) >= Math.abs(deltaY) ? 'x' : 'y';
      }

      if (axisLock === 'x' && event.cancelable) {
        event.preventDefault();
      }
    }, { passive: false });

    const finishSwipe = () => {
      if (!tracking) return;

      if (axisLock === 'x' && Math.abs(deltaX) >= swipeThreshold && Math.abs(deltaX) > Math.abs(deltaY)) {
        if (deltaX < 0) {
          onSwipeLeft();
        } else {
          onSwipeRight();
        }
      }

      resetState();
    };

    viewportEl.addEventListener('pointerup', finishSwipe, { passive: true });
    viewportEl.addEventListener('pointercancel', finishSwipe, { passive: true });
    viewportEl.addEventListener('pointerleave', finishSwipe, { passive: true });
  }

  function sanitizeFileName(text) {
    return String(text || 'result')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  function getScreenshotLayout(cardHeight) {
    if (window.matchMedia('(max-width: 768px)').matches) {
      const targetHeight = Math.round(window.innerHeight * 0.88);
      const baseHeight = cardHeight + (28 * 2);
      return {
        leftPadding: 18,
        rightPadding: 18,
        verticalPadding: 28,
        captureHeight: Math.max(baseHeight, targetHeight)
      };
    }

    if (window.matchMedia('(max-width: 1200px)').matches) {
      return {
        leftPadding: 45,
        rightPadding: 0,
        verticalPadding: 22,
        captureHeight: null
      };
    }

    return {
      leftPadding: 45,
      rightPadding: 0,
      verticalPadding: 20,
      captureHeight: null
    };
  }

  function canvasToBlob(canvas) {
    return new Promise((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (blob) {
          resolve(blob);
          return;
        }
        reject(new Error('Screenshot capture failed.'));
      }, 'image/png');
    });
  }

  async function captureSectionScreenshot(sectionElement) {
    if (typeof window.html2canvas !== 'function') {
      throw new Error('Screenshot tool is not available.');
    }

    const cardWidth = Math.ceil(sectionElement.offsetWidth);
    const cardHeight = Math.ceil(sectionElement.offsetHeight);
    const { leftPadding, rightPadding, verticalPadding, captureHeight } = getScreenshotLayout(cardHeight);
    const captureWidth = cardWidth + leftPadding + rightPadding;
    const captureShell = document.createElement('div');
    const sectionClone = sectionElement.cloneNode(true);

    captureShell.style.position = 'fixed';
    captureShell.style.left = '0';
    captureShell.style.top = '0';
    captureShell.style.zIndex = '-1';
    captureShell.style.pointerEvents = 'none';
    captureShell.style.padding = `${verticalPadding}px ${rightPadding}px ${verticalPadding}px ${leftPadding}px`;
    captureShell.style.background = '#ffffff';
    captureShell.style.width = `${captureWidth}px`;
    captureShell.style.boxSizing = 'border-box';

    if (captureHeight) {
      captureShell.style.height = `${captureHeight}px`;
      captureShell.style.display = 'flex';
      captureShell.style.alignItems = 'center';
      captureShell.style.justifyContent = 'center';
    }

    sectionClone.style.margin = '0';
    sectionClone.style.width = `${cardWidth}px`;
    sectionClone.style.boxSizing = 'border-box';
    sectionClone.style.boxShadow = 'none';
    sectionClone.querySelectorAll('.section-share-btn').forEach((node) => node.remove());

    captureShell.appendChild(sectionClone);
    document.body.appendChild(captureShell);

    try {
      const shellWidth = Math.ceil(captureShell.offsetWidth);
      const shellHeight = Math.ceil(captureShell.offsetHeight);
      return await window.html2canvas(captureShell, {
        backgroundColor: '#ffffff',
        scale: Math.min(2, window.devicePixelRatio || 1),
        useCORS: true,
        width: shellWidth,
        height: shellHeight,
        scrollX: 0,
        scrollY: 0
      });
    } finally {
      document.body.removeChild(captureShell);
    }
  }

  function downloadBlob(blob, filename) {
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(objectUrl);
  }

  function flashShareButtonState(button) {
    if (!button) return;
    const originalMarkup = button.dataset.originalMarkup || button.innerHTML;
    button.innerHTML = '<span>✓</span>';
    button.classList.add('copied');
    window.setTimeout(() => {
      button.innerHTML = originalMarkup;
      button.classList.remove('copied');
    }, 1200);
  }

  function initializeSectionShareButtons() {
    const shareButtons = document.querySelectorAll('.section-share-btn[data-share-section]');
    if (!shareButtons.length) return;

    shareButtons.forEach((button) => {
      button.dataset.originalMarkup = button.innerHTML;

      button.addEventListener('click', async () => {
        const sectionId = button.getAttribute('data-share-section');
        if (!sectionId) return;

        const sectionElement = document.getElementById(sectionId);
        if (!sectionElement) return;

        const sectionTitle = button.getAttribute('data-share-title') || 'My Compass Wrapped';
        const fileSafeTitle = sanitizeFileName(sectionTitle) || 'result';
        const fileName = `compass-wrapped-${fileSafeTitle}.png`;
        button.disabled = true;
        button.classList.add('is-loading');

        const shareText = `Check out my Compass Wrapped ${sectionTitle}`;

        try {
          const canvas = await captureSectionScreenshot(sectionElement);
          const screenshotBlob = await canvasToBlob(canvas);
          const screenshotFile = new File([screenshotBlob], fileName, { type: 'image/png' });

          const canShareFile = typeof navigator.canShare === 'function'
            && navigator.canShare({ files: [screenshotFile] });

          if (navigator.share && canShareFile) {
            await navigator.share({
              title: `Compass Wrapped: ${sectionTitle}`,
              text: shareText,
              files: [screenshotFile]
            });
          } else {
            downloadBlob(screenshotBlob, fileName);
          }

          flashShareButtonState(button);
        } catch (error) {
          if (error?.name === 'AbortError') {
            return;
          }
          window.alert('Could not create a screenshot for sharing. Please try again.');
        } finally {
          if (!button.classList.contains('copied')) {
            button.innerHTML = button.dataset.originalMarkup || button.innerHTML;
          }
          button.classList.remove('is-loading');
          button.disabled = false;
        }
      });
    });
  }

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

  initializeSectionShareButtons();

  // ========== END DEEPER STATS TOGGLE ==========

  // ========== LEFT SIDEBAR ==========
  const resultsSidebar = $('resultsSidebar');
  const sidebarToggle = $('sidebarToggle');
  const sidebarOverlay = $('sidebarOverlay');
  const sidebarDeeperToggle = $('sidebarDeeperToggle');
  const sidebarLinks = Array.from(document.querySelectorAll('.sidebar-link[data-section]'));

  const isSidebarCollapsed = () => resultsSidebar ? resultsSidebar.classList.contains('collapsed') : true;

  function applySidebarState(collapsed) {
    if (!resultsSidebar) return;
    resultsSidebar.classList.toggle('collapsed', collapsed);
    document.body.classList.toggle('sidebar-open', isPhoneMode() && !collapsed);
  }

  function openSidebar() {
    applySidebarState(false);
  }

  function closeSidebar() {
    applySidebarState(true);
  }

  function syncSidebarForViewport() {
    if (!resultsSidebar) return;

    if (isPhoneMode()) {
      if (!isSidebarCollapsed()) {
        document.body.classList.add('sidebar-open');
      } else {
        document.body.classList.remove('sidebar-open');
      }
      return;
    }

    document.body.classList.remove('sidebar-open');
    resultsSidebar.classList.remove('collapsed');
  }

  if (sidebarToggle && resultsSidebar) {
    sidebarToggle.addEventListener('click', () => {
      applySidebarState(!isSidebarCollapsed());
    });
  }

  if (sidebarOverlay) {
    sidebarOverlay.addEventListener('click', () => {
      if (isPhoneMode()) closeSidebar();
    });
  }

  if (resultsSidebar) {
    let edgeTracking = false;
    let edgePointerId = null;
    let edgeStartX = 0;
    let edgeStartY = 0;
    let edgeDeltaX = 0;
    let edgeDeltaY = 0;
    let edgeAxisLock = null;
    let edgeTouchTracking = false;
    let edgeTouchStartX = 0;
    let edgeTouchStartY = 0;

    const edgeStartThreshold = 10;
    const edgeSwipeThreshold = 70;

    const resetEdgeSwipe = () => {
      edgeTracking = false;
      edgePointerId = null;
      edgeStartX = 0;
      edgeStartY = 0;
      edgeDeltaX = 0;
      edgeDeltaY = 0;
      edgeAxisLock = null;
    };

    const isEdgeSwipeExcludedTarget = (target) => {
      if (!(target instanceof Element)) return false;
      if (target.closest('.carousel-viewport')) return true;
      if (target.closest('#section-transit-map, #section-awards')) return true;
      if (target.closest('button, a, input, select, textarea, label')) return true;
      return false;
    };

    document.addEventListener('pointerdown', (event) => {
      if (!isPhoneMode() || !isSidebarCollapsed() || !event.isPrimary) return;
      if (isEdgeSwipeExcludedTarget(event.target)) return;

      edgeTracking = true;
      edgePointerId = event.pointerId;
      edgeStartX = event.clientX;
      edgeStartY = event.clientY;
      edgeDeltaX = 0;
      edgeDeltaY = 0;
      edgeAxisLock = null;
    }, { passive: true });

    document.addEventListener('pointermove', (event) => {
      if (!edgeTracking || event.pointerId !== edgePointerId) return;

      edgeDeltaX = event.clientX - edgeStartX;
      edgeDeltaY = event.clientY - edgeStartY;

      if (!edgeAxisLock) {
        if (Math.abs(edgeDeltaX) < edgeStartThreshold && Math.abs(edgeDeltaY) < edgeStartThreshold) return;
        edgeAxisLock = Math.abs(edgeDeltaX) >= Math.abs(edgeDeltaY) ? 'x' : 'y';
      }

      if (edgeAxisLock === 'x' && event.cancelable) {
        event.preventDefault();
      }
    }, { passive: false });

    const finishEdgeSwipe = () => {
      if (!edgeTracking) return;

      if (
        edgeAxisLock === 'x' &&
        edgeDeltaX >= edgeSwipeThreshold &&
        Math.abs(edgeDeltaX) > Math.abs(edgeDeltaY)
      ) {
        openSidebar();
      }

      resetEdgeSwipe();
    };

    document.addEventListener('pointerup', finishEdgeSwipe, { passive: true });
    document.addEventListener('pointercancel', finishEdgeSwipe, { passive: true });

    document.addEventListener('touchstart', (event) => {
      if (!isPhoneMode() || !isSidebarCollapsed() || !event.touches.length) {
        edgeTouchTracking = false;
        return;
      }
      if (isEdgeSwipeExcludedTarget(event.target)) {
        edgeTouchTracking = false;
        return;
      }

      const touch = event.touches[0];
      edgeTouchStartX = touch.clientX;
      edgeTouchStartY = touch.clientY;
      edgeTouchTracking = true;
    }, { passive: true });

    document.addEventListener('touchend', (event) => {
      if (!edgeTouchTracking || !event.changedTouches.length) {
        edgeTouchTracking = false;
        return;
      }

      const touch = event.changedTouches[0];
      const deltaX = touch.clientX - edgeTouchStartX;
      const deltaY = touch.clientY - edgeTouchStartY;
      const isHorizontalSwipe = Math.abs(deltaX) > Math.abs(deltaY);

      if (isHorizontalSwipe && deltaX >= edgeSwipeThreshold) {
        openSidebar();
      }

      edgeTouchTracking = false;
    }, { passive: true });

    document.addEventListener('touchcancel', () => {
      edgeTouchTracking = false;
    }, { passive: true });

    bindSwipeCarousel(resultsSidebar, {
      onSwipeLeft: () => {
        if (isPhoneMode() && !isSidebarCollapsed()) closeSidebar();
      },
      onSwipeRight: () => {},
      isEnabled: () => isPhoneMode() && !isSidebarCollapsed(),
      ignoreInteractiveTargets: false
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
      if (isPhoneMode()) closeSidebar();
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

  if (resultsSidebar && isPhoneMode()) {
    closeSidebar();
  }

  window.addEventListener('resize', syncSidebarForViewport);
  syncSidebarForViewport();

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && isPhoneMode() && !isSidebarCollapsed()) {
      closeSidebar();
    }
  });

  updateActiveSidebarSection();

  // ========== END LEFT SIDEBAR ==========

  // ========== TOP STOPS MAP ==========
  try {
    const mapContainer = $('topStopsMap');
    const stationPoints = Array.isArray(data.top_station_map_points) ? data.top_station_map_points : [];
    const busPoints = Array.isArray(data.top_bus_stop_map_points) ? data.top_bus_stop_map_points : [];
    const specialTransitPoints = (Array.isArray(data.wce_lonsdale_stations) ? data.wce_lonsdale_stations : [])
      .filter((point) => Number(point.uses) > 0 && typeof point.lat === 'number' && typeof point.lon === 'number')
      .map((point) => ({
        ...point,
        markerType: point.type === 'seabus' ? 'seabus' : 'wce'
      }));
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
      const specialTransitMarkers = [];
      let specialTransitVisible = true;

      const createRankedIcon = (markerType, rank) => {
        const markerSize = isPhoneMode() ? 28 : 32;
        const markerAnchor = markerSize / 2;

        let markerContent = String(rank ?? '');
        if (markerType === 'wce') markerContent = '🚆';
        if (markerType === 'seabus') markerContent = '⛴';

        return L.divIcon({
        className: '',
        html: `<div class="ranked-map-marker ${markerType}"><span>${markerContent}</span></div>`,
        iconSize: [markerSize, markerSize],
        iconAnchor: [markerAnchor, markerAnchor],
        popupAnchor: [0, -markerAnchor]
      });
      };

      const markerZIndexOffset = (point) => {
        const typeBase = point.markerType === 'station'
          ? 22000
          : point.markerType === 'wce' || point.markerType === 'seabus'
            ? 16000
            : 10000;
        return typeBase + (100 - (point.rank || 0));
      };

      const createSpecialTransitIcon = (markerType) => L.icon({
        iconUrl: markerType === 'seabus' ? '/static/icons/seabus.svg' : '/static/icons/wce.svg',
        iconSize: isPhoneMode() ? [28, 28] : [32, 32],
        iconAnchor: isPhoneMode() ? [14, 14] : [16, 16],
        popupAnchor: [0, -14]
      });

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
        const displayedBounds = [
          ...rankedMarkers.filter(({ marker }) => map.hasLayer(marker)).map(({ marker }) => marker.getLatLng()),
          ...specialTransitMarkers.filter(({ marker }) => map.hasLayer(marker)).map(({ marker }) => marker.getLatLng())
        ];
        if (displayedBounds.length === 1) {
          map.setView(displayedBounds[0], 13);
          return;
        }
        if (displayedBounds.length > 1) {
          map.fitBounds(displayedBounds, { padding: [36, 36] });
        }
      };

      const addPointMarker = (point) => {
        let popupTitle = '';
        let popupMeta = '';

        if (point.markerType === 'station') {
          popupTitle = `Station #${point.rank}: ${point.name}`;
          popupMeta = `Uses: ${point.count}<br>Last used: ${point.last_used_display || 'Unknown'}${point.source_name ? `<br>Location source: ${point.source_name}` : ''}`;
        } else if (point.markerType === 'bus') {
          popupTitle = `Bus Stop #${point.rank}: ${point.name}`;
          popupMeta = `Stop #${point.stop_id}<br>Uses: ${point.count}<br>Last used: ${point.last_used_display || 'Unknown'}`;
        } else {
          popupTitle = `${point.markerType === 'seabus' ? 'SeaBus' : 'WCE'}: ${point.name}`;
          popupMeta = `Uses: ${point.uses}<br>Last used: ${point.last_used_display || 'Unknown'}`;
        }

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

      specialTransitPoints.forEach((point) => {
        const marker = L.marker([point.lat, point.lon], {
          icon: createSpecialTransitIcon(point.markerType),
          zIndexOffset: markerZIndexOffset(point)
        })
          .addTo(map)
          .bindPopup(
            `<div class="map-popup-title">${point.markerType === 'seabus' ? 'SeaBus' : 'WCE'}: ${point.name}</div><div class="map-popup-meta">Uses: ${point.uses}<br>Last used: ${point.last_used_display || 'Unknown'}</div>`
          );

        specialTransitMarkers.push({ marker, point });
      });

      fitDisplayedMarkers();

      requestAnimationFrame(() => {
        map.invalidateSize();
        updateOverlappingMarkerPositions();
      });

      map.on('zoomend', updateOverlappingMarkerPositions);

      const revealMoreStationsButton = $('revealMoreStations');
      if (revealMoreStationsButton && remainingStationPoints.length) {
        const stationRevealChunk = 5;
        let stationRankFrom = stationPoints.length
          ? stationPoints[stationPoints.length - 1].rank + 1
          : remainingStationPoints[0].rank;

        const updateStationButtonState = () => {
          const hasMore = remainingStationPoints.some((p) => p.rank >= stationRankFrom);
          if (!hasMore) {
            revealMoreStationsButton.disabled = true;
            revealMoreStationsButton.textContent = 'All Stations Revealed';
          } else {
            const nextBatch = remainingStationPoints.filter(
              (p) => p.rank >= stationRankFrom && p.rank < stationRankFrom + stationRevealChunk
            );
            revealMoreStationsButton.textContent = `Reveal Next ${nextBatch.length} Stations`;
          }
        };

        revealMoreStationsButton.addEventListener('click', () => {
          const nextBatch = remainingStationPoints
            .filter((p) => p.rank >= stationRankFrom && p.rank < stationRankFrom + stationRevealChunk)
            .map((point) => ({ ...point, markerType: 'station' }));

          nextBatch.forEach(addPointMarker);
          stationRankFrom += stationRevealChunk;

          fitDisplayedMarkers();
          updateOverlappingMarkerPositions();
          updateStationButtonState();
        });

        updateStationButtonState();
      }

      const revealMoreBusStopsButton = $('revealMoreBusStops');
      if (revealMoreBusStopsButton && remainingBusPoints.length) {
        const busRevealChunk = 10;
        let busRankFrom = busPoints.length
          ? busPoints[busPoints.length - 1].rank + 1
          : remainingBusPoints[0].rank;

        const updateBusButtonState = () => {
          const hasMore = remainingBusPoints.some((p) => p.rank >= busRankFrom);
          if (!hasMore) {
            revealMoreBusStopsButton.disabled = true;
            revealMoreBusStopsButton.textContent = 'All Bus Stops Revealed';
          } else {
            const nextBatch = remainingBusPoints.filter(
              (p) => p.rank >= busRankFrom && p.rank < busRankFrom + busRevealChunk
            );
            revealMoreBusStopsButton.textContent = `Reveal Next ${nextBatch.length} Bus Stops`;
          }
        };

        revealMoreBusStopsButton.addEventListener('click', () => {
          const nextBatch = remainingBusPoints
            .filter((p) => p.rank >= busRankFrom && p.rank < busRankFrom + busRevealChunk)
            .map((point) => ({ ...point, markerType: 'bus' }));

          nextBatch.forEach(addPointMarker);
          busRankFrom += busRevealChunk;

          fitDisplayedMarkers();
          updateOverlappingMarkerPositions();
          updateBusButtonState();
        });

        updateBusButtonState();
      }

      const toggleSpecialStopsButton = $('toggleSpecialStops');
      if (toggleSpecialStopsButton) {
        const updateSpecialToggleButton = () => {
          toggleSpecialStopsButton.textContent = specialTransitVisible
            ? 'Hide SeaBus/WCE Stops'
            : 'Reveal SeaBus/WCE Stops';
        };

        if (!specialTransitMarkers.length) {
          toggleSpecialStopsButton.disabled = true;
          toggleSpecialStopsButton.textContent = 'No SeaBus/WCE Stops Used';
        } else {
          updateSpecialToggleButton();
          toggleSpecialStopsButton.addEventListener('click', () => {
            specialTransitVisible = !specialTransitVisible;

            specialTransitMarkers.forEach(({ marker }) => {
              if (specialTransitVisible) {
                marker.addTo(map);
              } else {
                map.removeLayer(marker);
              }
            });

            fitDisplayedMarkers();
            updateOverlappingMarkerPositions();
            updateSpecialToggleButton();
          });
        }
      }
    }
  } catch (e) { console.error('top stops map error', e); }

  // ========== END TOP STOPS MAP ==========

  // ========== STATION CHART SORTING ==========
  let stationChart = null;
  let hourChart = null;
  let hourLabelsFull = [];
  let hourValuesFull = [];
  let hourRangeSelection = 'AM';
  let dayHourRangeSelection = 'AM';
  let currentStationSortMode = 'usage';

  function updateStationUsageChartHeight() {
    const stationWrapper = document.querySelector('.station-usage-chart');
    if (!stationWrapper || !Array.isArray(data.station_values)) return;

    const stationCount = Math.max(1, data.station_values.length);
    const perStationHeight = isPhoneMode() ? 21 : 35;
    stationWrapper.style.height = `${stationCount * perStationHeight}px`;

    if (stationChart) {
      stationChart.resize();
    }

    if (typeof updateCarouselHeight === 'function') {
      updateCarouselHeight();
    }
  }

  function shouldSplitHoursByMeridiem() {
    return isPhonePortrait();
  }

  function shouldSplitDayHourByMeridiem() {
    return isPhonePortrait();
  }

  function getDisplayedHourData() {
    if (!hourLabelsFull.length || !hourValuesFull.length) {
      return { labels: [], values: [] };
    }

    if (!shouldSplitHoursByMeridiem()) {
      return {
        labels: hourLabelsFull.map((hourValue) => formatHourLabel(hourValue, true)),
        values: [...hourValuesFull]
      };
    }

    const splitStart = hourRangeSelection === 'PM' ? 12 : 0;
    const splitEnd = splitStart + 12;

    return {
      labels: hourLabelsFull.slice(splitStart, splitEnd).map((hourValue) => formatHourLabel(hourValue, true)),
      values: hourValuesFull.slice(splitStart, splitEnd)
    };
  }

  function refreshHourRangeButtons() {
    const hourRangeControls = $('hourRangeControls');
    const amButton = $('hourRangeAM');
    const pmButton = $('hourRangePM');

    if (!hourRangeControls || !amButton || !pmButton) return;

    const showSplitButtons = shouldSplitHoursByMeridiem();
    hourRangeControls.style.display = showSplitButtons ? 'flex' : 'none';

    amButton.classList.toggle('active', hourRangeSelection === 'AM');
    pmButton.classList.toggle('active', hourRangeSelection === 'PM');
  }

  function updateHourChartData() {
    if (!hourChart) return;

    const displayedData = getDisplayedHourData();
    const isSplitView = shouldSplitHoursByMeridiem();

    hourChart.data.labels = displayedData.labels;
    hourChart.data.datasets[0].data = displayedData.values;
    hourChart.data.datasets[0].label = isSplitView
      ? `Trips by Hour (${hourRangeSelection})`
      : 'Trips by Hour (24h)';

    const fontSize = getBarChartFontSize();
    if (isSideView()) {
      hourChart.options.scales.x.ticks.autoSkip = false;
      hourChart.options.scales.x.ticks.maxTicksLimit = 24;
      hourChart.options.scales.x.ticks.callback = (_, index) => (
        index % 2 === 0 || index === displayedData.labels.length - 1
      ) ? (() => {
        if (!shouldSplitHoursByMeridiem()) {
          return formatHourLabel(hourLabelsFull[index], true);
        }
        const baseIndex = hourRangeSelection === 'PM' ? 12 : 0;
        return formatHourLabel(hourLabelsFull[baseIndex + index], true);
      })() : '';
    } else {
      hourChart.options.scales.x.ticks.autoSkip = false;
      hourChart.options.scales.x.ticks.maxTicksLimit = 24;
      hourChart.options.scales.x.ticks.callback = (_, index) => {
        if (!shouldSplitHoursByMeridiem()) {
          return formatHourLabel(hourLabelsFull[index], true);
        }
        const baseIndex = hourRangeSelection === 'PM' ? 12 : 0;
        return formatHourLabel(hourLabelsFull[baseIndex + index], true);
      };
    }
    hourChart.options.scales.x.ticks.font.size = fontSize;
    hourChart.options.scales.y.ticks.font.size = fontSize;
    hourChart.update();

    refreshHourRangeButtons();
    if (typeof updateCarouselHeight === 'function') {
      updateCarouselHeight();
    }
  }

  function getDisplayedDayHourData(hourLabels, fullValues) {
    if (!Array.isArray(hourLabels) || !Array.isArray(fullValues)) {
      return { labels: [], values: [] };
    }

    if (!shouldSplitDayHourByMeridiem()) {
      return {
        labels: hourLabels.map((hourValue) => formatHourLabel(hourValue, true)),
        values: [...fullValues]
      };
    }

    const splitStart = dayHourRangeSelection === 'PM' ? 12 : 0;
    const splitEnd = splitStart + 12;

    return {
      labels: hourLabels.slice(splitStart, splitEnd).map((hourValue) => formatHourLabel(hourValue, true)),
      values: fullValues.slice(splitStart, splitEnd)
    };
  }

  function refreshDayHourRangeButtons() {
    const controlGroups = document.querySelectorAll('.day-hour-range-controls');
    if (!controlGroups.length) return;

    const showSplitButtons = shouldSplitDayHourByMeridiem();
    controlGroups.forEach((group) => {
      group.style.display = showSplitButtons ? 'flex' : 'none';

      const amButton = group.querySelector('.day-hour-range-btn[data-range="AM"]');
      const pmButton = group.querySelector('.day-hour-range-btn[data-range="PM"]');
      if (amButton) amButton.classList.toggle('active', dayHourRangeSelection === 'AM');
      if (pmButton) pmButton.classList.toggle('active', dayHourRangeSelection === 'PM');
    });
  }

  function updateAllDayHourChartsData() {
    dayHourCharts.forEach((chart) => {
      const fullLabels = chart.$fullHourLabels || [];
      const fullValues = chart.$fullHourValues || [];
      const displayedData = getDisplayedDayHourData(fullLabels, fullValues);

      chart.data.labels = displayedData.labels;
      chart.data.datasets[0].data = displayedData.values;
      if (isSideView()) {
        chart.options.scales.x.ticks.autoSkip = false;
        chart.options.scales.x.ticks.maxTicksLimit = 24;
        chart.options.scales.x.ticks.callback = (_, index) => (
          index % 2 === 0 || index === displayedData.labels.length - 1
        ) ? (() => {
          if (!shouldSplitDayHourByMeridiem()) {
            return formatHourLabel(fullLabels[index], true);
          }
          const baseIndex = dayHourRangeSelection === 'PM' ? 12 : 0;
          return formatHourLabel(fullLabels[baseIndex + index], true);
        })() : '';
      } else {
        chart.options.scales.x.ticks.autoSkip = false;
        chart.options.scales.x.ticks.maxTicksLimit = 24;
        chart.options.scales.x.ticks.callback = (_, index) => {
          if (!shouldSplitDayHourByMeridiem()) {
            return formatHourLabel(fullLabels[index], true);
          }
          const baseIndex = dayHourRangeSelection === 'PM' ? 12 : 0;
          return formatHourLabel(fullLabels[baseIndex + index], true);
        };
      }
      chart.options.scales.x.ticks.font.size = getBarChartFontSize();
      chart.options.scales.y.ticks.font.size = getBarChartFontSize();

      chart.options.plugins.tooltip.callbacks = {
        title: (items) => {
          if (!items || !items.length) return '';
          const hourIndex = items[0].dataIndex;

          if (!shouldSplitDayHourByMeridiem()) {
            return formatHourLabel(fullLabels[hourIndex], false);
          }

          const baseIndex = dayHourRangeSelection === 'PM' ? 12 : 0;
          return formatHourLabel(fullLabels[baseIndex + hourIndex], false);
        }
      };

      chart.update('none');
    });

    refreshDayHourRangeButtons();
    if (typeof updateDayHourCarouselHeight === 'function') {
      updateDayHourCarouselHeight();
    }
  }
  
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
      const chartFontSize = getBarChartFontSize();
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
          scales: {
            x: { beginAtZero: true, ticks: { font: { size: chartFontSize } } },
            y: { ticks: { autoSkip: false, font: { size: chartFontSize } } }
          }
        }
      });

      bindAxisLabelTooltip(stationChart, { axis: 'y' });

      updateStationUsageChartHeight();
      window.addEventListener('resize', updateStationUsageChartHeight);
    }
  } catch (e) { console.error('station chart error', e); }

  try {
    const hourCanvas = $('hourChart');
    if (hourCanvas && data.hours && data.hour_values) {
      hourLabelsFull = [...data.hours];
      hourValuesFull = [...data.hour_values];

      const initialHourData = getDisplayedHourData();
      const hourFontSize = getBarChartFontSize();

      hourChart = new Chart(hourCanvas.getContext('2d'), {
        type: 'bar',
        data: {
          labels: initialHourData.labels,
          datasets: [{ label: 'Trips by Hour', data: initialHourData.values, backgroundColor: '#4da6ff' }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            tooltip: {
              enabled: true,
              callbacks: {
                title: (items) => {
                  if (!items || !items.length) return '';
                  const hourIndex = items[0].dataIndex;

                  if (!shouldSplitHoursByMeridiem()) {
                    return formatHourLabel(hourLabelsFull[hourIndex], false);
                  }

                  const baseIndex = hourRangeSelection === 'PM' ? 12 : 0;
                  return formatHourLabel(hourLabelsFull[baseIndex + hourIndex], false);
                }
              }
            },
            legend: { display: false }
          },
          scales: {
            x: {
              ticks: {
                autoSkip: false,
                maxTicksLimit: 24,
                callback: (_, index) => (
                  isSideView() && (index % 2 !== 0) && (index !== initialHourData.labels.length - 1)
                ) ? '' : (() => {
                  if (!shouldSplitHoursByMeridiem()) {
                    return formatHourLabel(hourLabelsFull[index], true);
                  }
                  const baseIndex = hourRangeSelection === 'PM' ? 12 : 0;
                  return formatHourLabel(hourLabelsFull[baseIndex + index], true);
                })(),
                maxRotation: 0,
                minRotation: 0,
                font: { size: hourFontSize }
              }
            },
            y: {
              beginAtZero: true,
              ticks: { font: { size: hourFontSize } }
            }
          }
        }
      });

      bindAxisLabelTooltip(hourChart, { axis: 'x' });

      refreshHourRangeButtons();

      const hourRangeAM = $('hourRangeAM');
      const hourRangePM = $('hourRangePM');

      if (hourRangeAM) {
        hourRangeAM.addEventListener('click', () => {
          hourRangeSelection = 'AM';
          updateHourChartData();
        });
      }

      if (hourRangePM) {
        hourRangePM.addEventListener('click', () => {
          hourRangeSelection = 'PM';
          updateHourChartData();
        });
      }

      window.addEventListener('resize', updateHourChartData);
    }
  } catch (e) { console.error('hour chart error', e); }

  try {
    const weekdayCanvas = $('weekdayChart');
    if (weekdayCanvas && data.days && data.weekday_values) {
      const chartFontSize = getBarChartFontSize();
      const weekdayChart = new Chart(weekdayCanvas.getContext('2d'), {
        type: 'bar',
        data: { labels: data.days, datasets: [{ label: 'Trips by Day', data: data.weekday_values, backgroundColor: '#4da6ff' }] },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { tooltip: { enabled: true }, legend: { display: false } },
          scales: {
            x: { ticks: { font: { size: chartFontSize } } },
            y: { beginAtZero: true, ticks: { font: { size: chartFontSize } } }
          }
        }
      });

      bindAxisLabelTooltip(weekdayChart, { axis: 'x' });
    }
  } catch (e) { console.error('weekday chart error', e); }

  try {
    const monthCanvas = $('monthChart');
    if (monthCanvas && data.month && data.month_values) {
      const chartFontSize = getBarChartFontSize();
      const monthChart = new Chart(monthCanvas.getContext('2d'), {
        type: 'bar',
        data: { labels: data.month, datasets: [{ label: 'Trips by Month', data: data.month_values, backgroundColor: '#4da6ff' }] },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { tooltip: { enabled: true }, legend: { display: false } },
          scales: {
            x: { ticks: { font: { size: chartFontSize } } },
            y: { beginAtZero: true, ticks: { font: { size: chartFontSize } } }
          }
        }
      });

      bindAxisLabelTooltip(monthChart, { axis: 'x' });
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

      const displayedData = getDisplayedDayHourData(hourLabels, values);

      const dayHourChart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
          labels: displayedData.labels,
          datasets: [{ label: `Trips by Hour (${dayName})`, data: displayedData.values, backgroundColor: '#4da6ff' }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            tooltip: {
              enabled: true,
              callbacks: {
                title: (items) => {
                  if (!items || !items.length) return '';
                  const hourIndex = items[0].dataIndex;

                  if (!shouldSplitDayHourByMeridiem()) {
                    return formatHourLabel(hourLabels[hourIndex], false);
                  }

                  const baseIndex = dayHourRangeSelection === 'PM' ? 12 : 0;
                  return formatHourLabel(hourLabels[baseIndex + hourIndex], false);
                }
              }
            },
            legend: { display: false }
          },
          scales: {
            x: {
              ticks: {
                autoSkip: false,
                maxTicksLimit: 24,
                callback: (_, index) => (
                  isSideView() && (index % 2 !== 0) && (index !== displayedData.labels.length - 1)
                ) ? '' : (() => {
                  if (!shouldSplitDayHourByMeridiem()) {
                    return formatHourLabel(hourLabels[index], true);
                  }
                  const baseIndex = dayHourRangeSelection === 'PM' ? 12 : 0;
                  return formatHourLabel(hourLabels[baseIndex + index], true);
                })(),
                maxRotation: 0,
                minRotation: 0,
                font: { size: getBarChartFontSize() }
              }
            },
            y: { beginAtZero: true, ticks: { font: { size: getBarChartFontSize() } } }
          }
        }
      });

      bindAxisLabelTooltip(dayHourChart, { axis: 'x' });

      dayHourChart.$fullHourLabels = [...hourLabels];
      dayHourChart.$fullHourValues = [...values];

      dayHourCharts.push(dayHourChart);
    });

    refreshDayHourRangeButtons();

    document.querySelectorAll('.day-hour-range-btn').forEach((button) => {
      button.addEventListener('click', () => {
        const selectedRange = button.getAttribute('data-range');
        if (selectedRange !== 'AM' && selectedRange !== 'PM') return;
        dayHourRangeSelection = selectedRange;
        updateAllDayHourChartsData();
      });
    });

    window.addEventListener('resize', updateAllDayHourChartsData);
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
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: getBarChartFontSize() } } } }
        }
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
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: getBarChartFontSize() } } } }
        }
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

  function setActiveSlideClass(slideNodes, activeIndex) {
    if (!slideNodes || !slideNodes.length) return;
    slideNodes.forEach((slide, index) => {
      slide.classList.toggle('active-slide', index === activeIndex);
    });
  }

  function updateCarouselHeight({ compensateScroll = false } = {}) {
    if (!slides || !slides.length || !carousel) return;
    const activeSlide = slides[currentSlide];
    const previousHeight = carousel.getBoundingClientRect().height;
    const nextHeight = activeSlide.scrollHeight;
    carousel.style.height = nextHeight + 'px';

    if (!compensateScroll || !isSwipeMode()) return;

    const shrinkAmount = previousHeight - nextHeight;
    if (shrinkAmount <= 40) return;

    const rect = carousel.getBoundingClientRect();
    const viewportBottom = window.innerHeight;
    const isInView = rect.top < viewportBottom && rect.bottom > 0;
    const isNearLowerPart = rect.bottom > viewportBottom - 120;

    if (isInView && isNearLowerPart) {
      window.scrollBy({
        top: -Math.min(shrinkAmount, 320),
        behavior: 'smooth'
      });
    }
  }

  function goToSlide(index) {
    if (!carousel) return;
    currentSlide = index;
    carousel.style.transform = `translateX(-${index * 100}%)`;
    setActiveSlideClass(slides, index);

    indicators.forEach((dot, i) => dot.classList.toggle('active', i === index));
    updateCarouselHeight({ compensateScroll: true });
  }

  function moveSlide(direction) {
    if (!slides || !slides.length) return;
    let newIndex = currentSlide + direction;
    if (newIndex < 0) newIndex = slides.length - 1;
    if (newIndex >= slides.length) newIndex = 0;
    goToSlide(newIndex);
  }

  function runUsageCarouselEntryAnimation() {
    if (!carousel || slides.length < 2) return;

    const originalTransition = carousel.style.transition;
    carousel.style.transition = 'none';
    goToSlide(1);

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        carousel.style.transition = originalTransition || 'transform 0.4s ease-in-out, height 0.45s cubic-bezier(0.22, 1, 0.36, 1)';
        moveSlide(-1);
      });
    });
  }

  // Expose functions (template uses inline onclick)
  window.goToSlide = goToSlide;
  window.moveSlide = moveSlide;

  // Initialize height and listeners
  updateCarouselHeight();
  window.addEventListener('resize', updateCarouselHeight);

  setTimeout(runUsageCarouselEntryAnimation, 80);

  const usageCarouselViewport = carousel ? carousel.closest('.carousel-viewport') : null;
  bindSwipeCarousel(usageCarouselViewport, {
    onSwipeLeft: () => moveSlide(1),
    onSwipeRight: () => moveSlide(-1),
    isEnabled: isSwipeMode
  });

  // -------------------------------
  // Day-hour Carousel (second carousel)
  // -------------------------------
  let currentDayHourSlide = 0;
  const dayHourCarousel = document.getElementById('dayHourCarousel');
  const dayHourSlides = dayHourCarousel ? dayHourCarousel.querySelectorAll('.day-hour-slide') : [];
  const dayHourIndicators = document.querySelectorAll('.day-hour-indicator');

  function updateDayHourCarouselHeight({ compensateScroll = false } = {}) {
    if (!dayHourSlides.length || !dayHourCarousel) return;
    const activeSlide = dayHourSlides[currentDayHourSlide];
    const previousHeight = dayHourCarousel.getBoundingClientRect().height;
    const nextHeight = activeSlide.scrollHeight;
    dayHourCarousel.style.height = nextHeight + 'px';

    if (!compensateScroll || !isSwipeMode()) return;

    const shrinkAmount = previousHeight - nextHeight;
    if (shrinkAmount <= 40) return;

    const rect = dayHourCarousel.getBoundingClientRect();
    const viewportBottom = window.innerHeight;
    const isInView = rect.top < viewportBottom && rect.bottom > 0;
    const isNearLowerPart = rect.bottom > viewportBottom - 120;

    if (isInView && isNearLowerPart) {
      window.scrollBy({
        top: -Math.min(shrinkAmount, 320),
        behavior: 'smooth'
      });
    }
  }

  function goToDayHourSlide(index) {
    if (!dayHourCarousel) return;
    currentDayHourSlide = index;
    dayHourCarousel.style.transform = `translateX(-${index * 100}%)`;
    setActiveSlideClass(dayHourSlides, index);

    dayHourIndicators.forEach((dot, i) => dot.classList.toggle('active', i === index));
    updateDayHourCarouselHeight({ compensateScroll: true });
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

  const dayHourCarouselViewport = dayHourCarousel ? dayHourCarousel.closest('.carousel-viewport') : null;
  bindSwipeCarousel(dayHourCarouselViewport, {
    onSwipeLeft: () => moveDayHourSlide(1),
    onSwipeRight: () => moveDayHourSlide(-1),
    isEnabled: isSwipeMode
  });

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

  function getAwardIndicatorsContainer(index) {
    return document.getElementById(`awardIndicators${index}`);
  }

  function getAwardMaxIndex(track) {
    if (!track) return 0;
    const cardCount = track.children.length;
    const cardsPerPage = 2;
    const totalPages = Math.ceil(cardCount / cardsPerPage);
    return Math.max(0, totalPages - 1);
  }

  function renderAwardIndicators(index, maxIndex) {
    const indicatorsContainer = getAwardIndicatorsContainer(index);
    if (!indicatorsContainer) return;

    const targetCount = maxIndex + 1;
    const currentCount = indicatorsContainer.children.length;
    if (currentCount === targetCount) return;

    indicatorsContainer.innerHTML = '';
    for (let pageIndex = 0; pageIndex <= maxIndex; pageIndex += 1) {
      const dot = document.createElement('button');
      dot.type = 'button';
      dot.className = 'award-indicator';
      dot.setAttribute('aria-label', `Go to award slide ${pageIndex + 1}`);
      dot.addEventListener('click', () => {
        window.goToAwardSlide(index, pageIndex);
      });
      indicatorsContainer.appendChild(dot);
    }
  }

  function updateAwardIndicators(index, activeIndex) {
    const indicatorsContainer = getAwardIndicatorsContainer(index);
    if (!indicatorsContainer) return;

    Array.from(indicatorsContainer.children).forEach((dot, dotIndex) => {
      dot.classList.toggle('active', dotIndex === activeIndex);
    });
  }

  function updateAwardCarousel(index) {
    const track = getAwardTrack(index);
    if (!track || !track.children.length) return;

    const computedStyles = window.getComputedStyle(track);
    const gap = parseFloat(computedStyles.gap || computedStyles.columnGap || '0') || 0;
    const cardWidth = track.children[0].getBoundingClientRect().width;
    const maxIndex = getAwardMaxIndex(track);
    const cardsPerPage = 2;

    if (!Object.prototype.hasOwnProperty.call(awardCarouselState, index)) {
      awardCarouselState[index] = 0;
    }

    awardCarouselState[index] = Math.max(0, Math.min(awardCarouselState[index], maxIndex));

    const offsetX = awardCarouselState[index] * cardsPerPage * (cardWidth + gap);
    track.style.transform = `translateX(-${offsetX}px)`;

    renderAwardIndicators(index, maxIndex);
    updateAwardIndicators(index, awardCarouselState[index]);

    const prevButton = getAwardButton(index, 'Prev');
    const nextButton = getAwardButton(index, 'Next');
    if (prevButton) prevButton.disabled = false;
    if (nextButton) nextButton.disabled = false;
  }

  window.goToAwardSlide = function(index, pageIndex) {
    const track = getAwardTrack(index);
    if (!track || !track.children.length) return;

    const maxIndex = getAwardMaxIndex(track);
    awardCarouselState[index] = Math.max(0, Math.min(pageIndex, maxIndex));
    updateAwardCarousel(index);
  };

  window.moveAwardSlide = function(index, direction) {
    const track = getAwardTrack(index);
    if (!track || !track.children.length) return;

    const maxIndex = getAwardMaxIndex(track);
    if (maxIndex <= 0) {
      awardCarouselState[index] = 0;
      updateAwardCarousel(index);
      return;
    }

    if (!Object.prototype.hasOwnProperty.call(awardCarouselState, index)) {
      awardCarouselState[index] = 0;
    }

    const loopSize = maxIndex + 1;
    const nextIndex = awardCarouselState[index] + direction;
    awardCarouselState[index] = ((nextIndex % loopSize) + loopSize) % loopSize;
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

  const awardViewports = document.querySelectorAll('.award-carousel-viewport');
  awardViewports.forEach((viewport) => {
    const track = viewport.querySelector('.award-carousel-track');
    if (!track || !track.id) return;

    const index = Number(track.id.replace('awardCarouselTrack', ''));
    if (Number.isNaN(index)) return;

    bindSwipeCarousel(viewport, {
      onSwipeLeft: () => window.moveAwardSlide(index, 1),
      onSwipeRight: () => window.moveAwardSlide(index, -1),
      isEnabled: isSwipeMode
    });
  });

  window.addEventListener('resize', () => {
    Object.keys(awardCarouselState).forEach((index) => {
      updateAwardCarousel(Number(index));
    });
  });
});