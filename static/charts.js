// static/js/charts.js

// Wait until DOM loaded
document.addEventListener("DOMContentLoaded", () => {
    const barContainer = document.getElementById("barGraph");

    if (barContainer) {
        const labels = JSON.parse(barContainer.dataset.labels);
        const values = JSON.parse(barContainer.dataset.values);

        new Chart(barContainer, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    label: "Counts",
                    data: values
                }]
            },
            options: {
                indexAxis: "y", // horizontal bar graph
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }
});
