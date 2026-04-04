async function deleteReceipt(receiptId){

    //popup pomocou kniznice
    const result = await Swal.fire({
        title: "Naozaj chcete odtrániť tento bloček?",
        text: "Táto akcia sa nedá vrátiť.",
        icon: "warning",     
        showCancelButton: true,
        confirmButtonText: "Áno",
        cancelButtonText: "Zrušiť",
        confirmButtonColor: "#e74c3c",
        cancelButtonColor: "#aaa",
    });
    
    if (!result.isConfirmed){
        return;
    }

    try {
        const response = await fetch(`/delete_receipt/${receiptId}`, { method: 'DELETE' });
        const data = await response.json();

        if (data.success) {

            //odstranime
            document.getElementById(`receipt-${receiptId}`).remove();

            //ak je otvoreny detail tak zatvor aj ten
            const detail = document.getElementById(`detail-${receiptId}`);
            if (detail) detail.remove();

            Swal.fire({
                toast: true,
                position: "top-end",
                title: "Úspešne odstránené!",
                icon: "success",
                timer: 1500,      
                showConfirmButton: false,
            });
        }

    } catch (error) {
        console.error("Chyba:",error)

        Swal.fire({
                toast: true,
                position: "top-end",
                title: "Bloček sa nepodarilo odstrániť.",
                icon: "error",
                timer: 1500,      
                showConfirmButton: false,
        });
    }
}

async function showDetails(receiptId){
    
    //ak uz je otvoreny, zavrieme

    const opened = document.getElementById(`detail-${receiptId}`);
    if (opened){
        opened.remove();
        return;
    }
    //posleme na flask cakame na odpoved
    const response = await fetch(`/receipt_details/${receiptId}`);
    const items = await response.json();

    //vytorime novy div naplnime
    const itemsDetail = document.createElement('div');
    itemsDetail.id = `detail-${receiptId}`;
    itemsDetail.className = 'receipt_detail';

    //pomocou tabulky
    let html = `
        <table class="detail_table">
            <thead>
                <tr>
                    <th>Názov</th>
                    <th>Množstvo</th>
                    <th>Kategória</th>
                    <th>Cena</th>
                </tr>
            </thead>
            <tbody>
    `;

    //naplnime vsetkymi itemami
    items.forEach(item => {
        html += `
            <tr>
                <td>${item.item_name}</td>
                <td>${item.amount}</td>
                <td>${item.category}</td>
                <td>${item.prize}€</td>
            </tr>
        `;
    });

    //pridame koncove tagy
    html += `</tbody></table>`;
    itemsDetail.innerHTML = html;

    //zoberieme blocek podla id, aby sme ho spravne zobrazili, a dame hned za neho
    const receiptEl = document.getElementById(`receipt-${receiptId}`);
    receiptEl.insertAdjacentElement('afterend', itemsDetail);
}

async function showOrigin(receiptId){

    const url = `/receipt_file/${receiptId}`
    //posleme flasku
    const response = await fetch(url, {
        method: 'HEAD' 
    });

    if (!response.ok) {
        Swal.fire({
            title: "Súbor sa nenašiel.",
            icon: "error",
        })
        return;
    }

    const contentType = response.headers.get('Content-Type') || '';
    let previewHTML;

    // ak pdf zak zobrazime cez iframe
    if (contentType.includes('pdf')) {
        previewHTML = `
            <div class="receipt-preview-wrapper pdf-preview-wrapper">
                <iframe src="${url}#zoom=page-width" class="receipt-preview-frame"></iframe>
            </div>
`;
    }

    // obrazok zobrazjeme cez img
    else if (contentType.includes('image')) {
        previewHTML = `
            <div class="receipt-preview-wrapper image-preview-wrapper">
                <img src="${url}" class="receipt-preview-image">
            </div>
        `;
    }

    // nerozpnonany subor otvorime na novom okne
    else {
        window.open(url, '_blank');
        return;
    }

    Swal.fire({
        html: previewHTML,
        width: '90vw',
        padding: '0.75rem',
        showConfirmButton: false,
        showCloseButton: true,
        customClass: {
            popup: 'receipt-preview-popup',
            htmlContainer: 'receipt-preview-html'
        }
    });
}   

async function importEmailReceipts() {

    const confirmResult = await Swal.fire({
        title: "Prehľadať emaily?",
        text: "Aplikácia vyhľadá PDF bločky podľa filtrov uložených v nastaveniach.",
        icon: "question",
        showCancelButton: true,
        confirmButtonText: "Áno",
        cancelButtonText: "Zrušiť",
        confirmButtonColor: "#16a34a",
        cancelButtonColor: "#aaa"
    });

    if (!confirmResult.isConfirmed) {
        return;
    }

    Swal.fire({
        title: "Prehľadávam emaily...",
        text: "Prosím počkajte",
        allowOutsideClick: false,
        allowEscapeKey: false,
        showConfirmButton: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    try {
        const response = await fetch("/import-email-receipts", {
            method: "POST"
        });

        const data = await response.json();

        Swal.close();

        if (!data.success) {
            Swal.fire({
                icon: "error",
                title: "Chyba",
                text: data.message || "Import emailov sa nepodaril."
            });
            return;
        }

        const results = data.results || [];

        if (results.length === 0) {
            Swal.fire({
                icon: "info",
                title: "Nenašli sa žiadne bločky",
                text: "Skontrolujte filtre alebo emaily s PDF prílohami."
            });
            return;
        }

        const imported = results.filter(r => r.status === "imported").length;
        const duplicate = results.filter(r => r.status === "duplicate").length;
        const failed = results.filter(r => r.status === "failed").length;

        Swal.fire({
            icon: failed > 0 ? "warning" : "success",
            title: "Import dokončený",
            html: `
                <div style="text-align:left">
                    ✔ Uložené: <b>${imported}</b><br>
                    ⚠ Duplicitné: <b>${duplicate}</b><br>
                    ❌ Neúspešné: <b>${failed}</b>
                </div>
            `
        }).then(() => {
            if (imported > 0) {
                location.reload();
            }
        });

    } catch (error) {
        Swal.close();
        console.error("Chyba:", error);

        Swal.fire({
            icon: "error",
            title: "Chyba",
            text: "Nepodarilo sa spojiť so serverom."
        });
    }
}