document.addEventListener("DOMContentLoaded", function () {
    initExpensesChart();
    initCategoryChart();
});

function initExpensesChart(){

    const canvas = document.getElementById('ExpensesChart');

    if (!canvas) return;

    new Chart(canvas, {
        type: "bar",
        data: {
            labels:  dailyExpensesLabels,
            datasets: [{
                label: "Výdavky (€)",
                data: dailyExpensesValues,
                backgroundColor: "rgba(155, 92, 240, 0.7)",
                borderColor: "rgba(155, 92, 240, 1)",
                borderWidth: 1,
                borderRarius: 8

            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend:  {
                    display: true

                }
            },
            scales: {
                x: {
                    title: {
                        display:    true,
                        text: "Ďen v mesiaci"
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
function initCategoryChart() {

    const canvas = document.getElementById('CategoryChart');

    if (!canvas) return;

    new Chart(canvas, {
        type: 'pie',
        data: {
            labels: categoryLabels,
            datasets: [{
                data: categoryValues,
                backgroundColor: [
                    '#7c5ce6',
                    '#60a5fa',
                    '#f472b6',
                    '#facc15',
                    '#34d399',
                    '#fb7185'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.raw || 0;

                            return `${label}: ${value} €`;
                        }
                    }
                }
            }
        }
    });
}

async function categorizeItems() {

    
    // potvrdenie
    const confirmResult = await Swal.fire({
        title: "Chcete doplniť kategórie?",
        text: "Spracujú sa všetky nezaradené položky.",
        icon: "question",
        showCancelButton: true,
        confirmButtonText: "Áno",
        cancelButtonText: "Zrušiť",
        confirmButtonColor: "#e65c5c",
        cancelButtonColor: "#aaa"
    });

    if (!confirmResult.isConfirmed) {
        return;
    }

    const controller = new AbortController();

    Swal.fire({
        title: "AI kategorizuje položky...",
        text: "Môže to trvať dlhšie, prosím počkajte... (10)",
        allowOutsideClick: false,
        allowEscapeKey: false,
        showConfirmButton: false,
        didOpen: () => {

            let secondsLeft = 10;

            interval = setInterval(() => {
                secondsLeft--;

                if (secondsLeft > 0) {
                    Swal.update({
                        text: `Môže to trvať dlhšie, prosím počkajte... (${secondsLeft})`
                    });
                } else {
                    clearInterval(interval);
                    interval = null;

                    Swal.update({
                        text: "Spracovanie trvá dlhšie...",
                        showConfirmButton: true,
                        confirmButtonText: "Zrušiť čakanie",
                        confirmButtonColor: "#dc0d1e"
                    });
                }
            }, 1000);
        }
    }).then((result) => {
        if (result.isConfirmed) {
            controller.abort();

            Swal.fire({
                icon: "info",
                title: "Čakanie zrušené",
                text: "Požiadavka bola zrušená v aplikácii."
            });
        }
    });

    try {
        const response = await fetch("/categorize_all_items", {
            method: "POST"
        });

        if (interval) {
            clearInterval(interval);
            interval = null;
        }


        const data = await response.json();

        Swal.close();

        if (data.success) {

            await Swal.fire({
                icon: "success",
                title: "Hotovo",
                text: data.message
            });

            location.reload();
        }
        else {
            Swal.fire({
                icon: "error",
                title: "Chyba",
                text: data.error || "Kategorizácia zlyhala, skontrolujte interetové pripojenie."
            });
        }

    } catch (error) {

        if (interval) {
            clearInterval(interval);
            interval = null;
        }

        Swal.close();

        console.error("Chyba:", error);

        Swal.fire({
            icon: "error",
            title: "Chyba",
            text: "Nepodarilo sa spojiť so serverom."
        });
    }
}