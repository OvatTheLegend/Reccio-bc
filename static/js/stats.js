document.addEventListener("DOMContentLoaded", function () {
    initMonthlyChart();
    initCategoryExpensesChart();
    initShopChart();
});

function initMonthlyChart() {

    const canvas = document.getElementById('monthlyExpensesChart');
    if (!canvas) return;

    new Chart(canvas, {
        type: "bar",
        data: {
            labels: monthlyLabels,
            datasets: [{
                label: "Výdavky (€)",
                data: monthlyValues,
                backgroundColor: "rgba(124, 92, 230, 0.7)",
                borderColor: "rgba(124, 92, 230, 1)",
                borderWidth: 1,
                borderRadius: 8,
                barPercentage: 0.6,
                categoryPercentage: 0.6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: "Mesiac"
                    }
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: "Suma (€)"
                    }
                }
            }
        }
    });
}

function initCategoryExpensesChart() {

    const canvas = document.getElementById("categoryExpensesChart");
    if (!canvas) return;

    new Chart(canvas, {
        type: "pie",
        data: {
            labels: categoryLabels,
            datasets: [{
                data: categoryValues,
                backgroundColor: [
                    "#7c5ce6",
                    "#60a5fa",
                    "#f472b6",
                    "#facc15",
                    "#34d399",
                    "#fb7185",
                    "#9ca3af"
                ],
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "bottom"
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || "";
                            const value = context.raw || 0;

                            return `${label}: ${value.toFixed(2)} €`;
                        }
                    }
                }
            }
        }
    });
}

function initShopChart() {

    const canvas = document.getElementById("shopExpensesChart");
    if (!canvas) return;

    new Chart(canvas, {
        type: "bar",
        data: {
            labels: shopLabels,
            datasets: [{
                label: "Výdavky (€)",
                data: shopValues,
                backgroundColor: "rgba(96, 165, 250, 0.7)",
                borderColor: "rgba(96, 165, 250, 1)",
                borderWidth: 1,
                borderRadius: 8,
                barPercentage: 0.6,
                categoryPercentage: 0.6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.raw + " €";
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: "Obchod"
                    }
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: "Suma (€)"
                    }
                }
            }
        }
    });
}