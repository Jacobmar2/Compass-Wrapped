document.addEventListener('DOMContentLoaded', () => {
  const data = window.resultsData || {};

  // Helper: safe get element
  const $ = (id) => document.getElementById(id);

  // -------------------------------
  // Charts (create only if canvas exists)
  // -------------------------------
  try {
    const stationCanvas = $('stationChart');
    if (stationCanvas && data.station_labels && data.station_values) {
      new Chart(stationCanvas.getContext('2d'), {
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

  // -------------------------------
  // Carousel
  // -------------------------------
  let currentSlide = 0;
  const carousel = document.getElementById('carousel');
  const slides = document.querySelectorAll('.slide');
  const indicators = document.querySelectorAll('.indicator');

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
});