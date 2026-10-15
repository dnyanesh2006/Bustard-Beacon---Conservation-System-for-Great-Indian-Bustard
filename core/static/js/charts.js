/* BUSTARD BEACON — Chart.js Data Visualization Engine */

document.addEventListener("DOMContentLoaded", function() {
    fetch("/api/analytics-data/")
        .then(res => res.json())
        .then(data => {
            // 1. Incident Category Distribution Chart
            const catCtx = document.getElementById("incidentCategoryChart");
            if (catCtx) {
                new Chart(catCtx, {
                    type: 'doughnut',
                    data: {
                        labels: data.categories.labels,
                        datasets: [{
                            data: data.categories.data,
                            backgroundColor: ['#e53935', '#fb8c00', '#1e88e5', '#43a047', '#8e24aa', '#3949ab', '#00acc1'],
                            borderWidth: 1,
                            borderColor: '#141f1c'
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'bottom', labels: { color: '#a3b8b0' } }
                        }
                    }
                });
            }

            // 2. Zone Incident Distribution Chart
            const zoneCtx = document.getElementById("zoneIncidentChart");
            if (zoneCtx) {
                new Chart(zoneCtx, {
                    type: 'bar',
                    data: {
                        labels: data.zones.labels,
                        datasets: [{
                            label: 'Incidents per Zone',
                            data: data.zones.data,
                            backgroundColor: '#2e7d32',
                            borderColor: '#81c784',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            y: { beginAtZero: true, ticks: { color: '#a3b8b0' }, grid: { color: '#2c3e38' } },
                            x: { ticks: { color: '#a3b8b0' }, grid: { color: '#2c3e38' } }
                        },
                        plugins: {
                            legend: { display: false }
                        }
                    }
                });
            }

            // 3. Provenance Ratio Chart
            const provCtx = document.getElementById("provenanceRatioChart");
            if (provCtx) {
                new Chart(provCtx, {
                    type: 'pie',
                    data: {
                        labels: data.provenance.labels,
                        datasets: [{
                            data: data.provenance.data,
                            backgroundColor: ['#2e7d32', '#1e88e5'],
                            borderWidth: 1,
                            borderColor: '#141f1c'
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'bottom', labels: { color: '#a3b8b0' } }
                        }
                    }
                });
            }
        })
        .catch(err => console.error("Error loading analytics JSON data:", err));
});
