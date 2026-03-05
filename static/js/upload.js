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

async function uploadReceipt(){

    const file = document.getElementById('receipt_file');

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
    formData.append('receipt_file', file.files[0])

    try {
        //posleme cez flask
        const response = await fetch('/upload', {
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