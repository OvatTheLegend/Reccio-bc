/* funckia na prepianie medzi manual a pdf formularom*/

function switchOption(option){

    const pdf = document.getElementById('pdf-option');
    const manual = document.getElementById('manual-option');
    const photo = document.getElementById('photo-option')

    /*konkretne tlacidla v navigacii*/
    const nav_pdf = document.getElementById('nav-pdf')
    const nav_manual = document.getElementById('nav-manual')
    const nav_photo = document.getElementById('nav-photo')

    /*zistenie co ktory button vyvolal funkciu*/
    /*pdf*/
    if (option == 'pdf'){
        pdf.style.display = 'block';
        photo.style.display = 'none'
        manual.style.display = 'none';

        nav_pdf.classList.add('active');
        nav_manual.classList.remove('active');
        nav_photo.classList.remove('active')
    }

    /*fotka*/
    else if (option == 'photo') {
        photo.style.display = 'block'
        pdf.style.display = 'none';
        manual.style.display = 'none';

        nav_photo.classList.add('active')
        nav_pdf.classList.remove('active');
        nav_manual.classList.remove('active');

    }

    /*manualne*/
    else {
        manual.style.display = 'block';
        pdf.style.display = 'none';
        photo.style.display = 'none'
        
        nav_manual.classList.add('active');
        nav_pdf.classList.remove('active');
        nav_photo.classList.remove('active')
        
    }
}

async function upload_pdf(){

    const file = document.getElementById('receipt_file_pdf');

    //ak nie je vybraty subor -> warning
    if (!file.files[0]) {
        Swal.fire({
            tittle: "Nie je vybratý žiadny súbor",
            icon: "warning",
            text: "najprv vyber súbor!",
        });
        return;
    }

    //do formData vlozime prilozeny subor
    const formData = new FormData();
    formData.append('receipt_file_pdf', file.files[0])

    // cakanie na nahranie blocku
    Swal.fire({
        title: "Spracovávam bloček...",
        text: "Prosím počkajte",
        allowOutsideClick: false,
        allowEscapeKey: false,
        showConfirmButton: false,
        didOpen: () => Swal.showLoading()
    });

    try {
        //posleme cez flask
        const response = await fetch('/upload_pdf', {
            method: 'POST',
            body: formData,
        });

        const data = await response.json();

        if (data.success) {
            Swal.fire({
                toast: true,
                position: "top-end",
                icon: "success",
                title: data.message,
                showConfirmButton: false,
                timer: 2500,
            });
        }

        else {
            Swal.fire({
                icon: "error",
                title: "Chyba",
                text: data.message,
            });
        }
    } catch (error) {
        console.error("Chyba:", error);
    }
}

async function upload_img(){

    const file = document.getElementById('receipt_file_img');

    //ak nie je vybraty subor -> warning
    if (!file.files[0]) {
        Swal.fire({
            tittle: "Nie je vybratá žiadna fotka",
            icon: "warning",
            text: "najprv vyberte fotku!",
        });
        return;
    }

    //do formData vlozime prilozeny subor
    const formData = new FormData();
    formData.append('receipt_file_img', file.files[0])

    //controller pre umozenenie zrusenie pouzivatelovi
    const controller = new AbortController();

    // cakanie na nahranie blocku
    Swal.fire({
        title: "Spracovávam fotku...",
        text: "Prosím počkajte",
        allowOutsideClick: false,
        allowEscapeKey: false,
        showConfirmButton: false,
        didOpen: () => {
            Swal.showLoading();

            //odpocitavanie sekund do umoznenia zrusenia spracovania
            let secondsLeft = 5;
            const interval = setInterval(() => {
                secondsLeft--;

            Swal.update({
                text: `Prosím počkajte... (${secondsLeft})`,
            })

            if (secondsLeft <= 0){
                clearInterval(interval);
                Swal.update({
                    text: "Spracovanie trvá dlhšie...",
                    showConfirmButton: true,
                    confirmButtonText: "Zrušiť",
                    confirmButtonColor: "#dc0d1e",
                });
            }
        }, 1000);
        }

    }).then((result) => {
        if (result.isConfirmed){
            controller.abort();
            Swal.fire({
                icon: 'info',
                title: 'Zrušené',
                text: 'Nahrávanie bolo zrušené'
            });
        }
    });

    try {
        //posleme cez flask
        const response = await fetch('/upload_img', {
            method: 'POST',
            body: formData,
            signal: controller.signal
        });

        const data = await response.json();

        if (data.success) {
            Swal.fire({
                toast: true,
                position: "top-end",
                icon: "success",
                title: data.message,
                showConfirmButton: false,
                timer: 2500,
            });
        }

        else {
            Swal.fire({
                icon: "error",
                title: "Chyba",
                text: data.message,
            });
        }

    } catch (error) {
        //ak pouzivatel klikol na zrusiť
        if (error.name === 'AbortError'){
            return;
        }

        console.error("Chyba:", error);
    }   
}

function toggleCustomShop() {
    //najdeme nas select
    const select = document.getElementById('manual_shop');
    const custom = document.getElementById('manual_shop_custom');

    //ak ma byt custom, tak nastavime
    custom.style.display = select.value === 'ine' ? 'block' : 'none';
}

let itemCount = 0;


function addItem(){
    //navysime itemCount
    itemCount += 1;
    const container = document.getElementById('manual_items');

    //vytvorime novy div a dame polozke id
    const item = document.createElement('div');
    
    //pridame do zoznamu
    item.classList.add('manual_item');
    item.id = `item_${itemCount}`;

    //teraz pridame inputy pre nas blocek
    item.innerHTML = `
        
        <input type="text" placeholder="Názov položky" class="item_name">
        <input type="number" placeholder="Množstvo" class="item_amount" step="0.01" min="0">
        <input type="number" placeholder="Cena (€)" class="item_prize" step="0.01" min="0">
        <button type="button" onclick="removeItem(${itemCount})">✕</button>     

    `;
    
    //a pridame do stranky
    container.appendChild(item);
}

function removeItem(id) {
    //vymazeme prislusnu polozku
    document.getElementById(`item_${id}`).remove();
}

async function uploadManual(){
    //najrpv ziskame vsetky potrebne hodnoty
    const shopSelect = document.getElementById('manual_shop').value;
    const shopCustom = document.getElementById('manual_shop_custom').value.trim();
    const shop = shopSelect === 'ine' ? shopCustom : shopSelect;
    const date = document.getElementById('manual_date').value.trim();
    const time = document.getElementById('manual_time').value.trim();
    const prize = document.getElementById('manual_prize').value;

    //nasledne ich zvalidujeme

    //aby obchod musel byt zadany
    if (!shop) {
        Swal.fire({ 
            icon: 'warning', 
            title: 'Zadajte názov obchodu' }); 
        return;
    }

    if (shop.length >= 15){
        Swal.fire({ 
            icon: 'warning', 
            title: 'Uveďte kratší nazov obchodu',
            text: 'max 15 znakov'
        })
        return;
    }

    //aby sedel datum s nasim formatom ktory ide do databazy
    if (!date || !/^\d{2}\.\d{2}\.\d{4}$/.test(date)) {

        Swal.fire({ 
            icon: 'warning', 
            title: 'Nesprávny formát dátumu', 
            text: 'DD.MM.YYYY'}); 
        return;
    }

    //aby sedel cas
    if (!time || !/^\d{2}:\d{2}:\d{2}$/.test(time)) {

        Swal.fire({ icon: 'warning', title: 'Nesprávny formát času', text: 'HH:MM:SS'}); 
        return;
    }

    //aby nebola nulova cena
    if (!prize || parseFloat(prize) <= 0) {

        Swal.fire({ icon: 'warning', title: 'Suma musí byť kladná' }); 

        return;
    }

    //teraz polozky blocku, ak neni ani jedna tak upozornenie
    const itemDivs = document.querySelectorAll('.manual_item');
    if (itemDivs.length === 0) {

        Swal.fire({icon: 'warning', title: 'Pridaj aspoň jednu položku' }); 
        return;
    }

    //prejdeme cez vsetky a skontrolujeme
    const items = [];
    for (const div of itemDivs){

        //najdeme polozky
        const name = div.querySelector('.item_name').value.trim();
        const amount = div.querySelector('.item_amount').value;
        const itemPrize = div.querySelector('.item_prize').value;

        //zvalidujeme ich

        if (!name || !amount || !itemPrize) {
            Swal.fire({ icon: 'warning', title: 'Vypľnte všetky polia položky!' }); return;
        }

        //pushneme na koniec nasho pola
        items.push({
            item_name: name,
            amount: parseFloat(amount),
            prize: parseFloat(itemPrize),
        });
    }

    //teraz posleme na flask
    try {
        const response = await fetch('/upload_manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                shop_name: shop,
                date: date,
                time: time,
                prize: parseFloat(prize),
                items: items,

            })
        });

        //cakame na odpoved s flasku
        const data = await response.json();

        //ak vsetko prebehlo v poriadku
        if (data.success){
            Swal.fire({
                toast: true,
                position: "top-end",
                icon: "success",
                title: data.message,
                showConfirmButton: false,
                timer: 2500,
            });
        }

        //inak error
        else {
            Swal.fire({
                icon: 'error',
                title: 'Chyba',
                text: data.message
            });
        }

    } catch (error) {
        console.error("Chyba:", error);
    }

}