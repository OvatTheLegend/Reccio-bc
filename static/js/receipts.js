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

    //pre pdf -iframe
    if (contentType.includes('pdf')) {
        previewHTML = `<iframe src="${url}" width="100%" height="100%" style="border:none;"></iframe>`;
    
    // pre img - img tag
    } else if (contentType.includes('image')) {
        previewHTML = `<img src="${url}" style="max-width:100%; max-height:100%; object-fit:contain;">`;

    // ak nepozname, tak nove okno
    } else {
        window.open(url, '_blank');
        return;
    }

    Swal.fire({
        html: previewHTML,      
        width: "100%",           
        padding: "0",          
        showConfirmButton: false,
        showCloseButton: true,    
        customClass: {
        popup: 'receipt-preview-popup',  
        htmlContainer: 'receipt-preview-html'
        }
    });
}   