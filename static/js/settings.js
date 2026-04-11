document.addEventListener("DOMContentLoaded", function () {

    //pre meno
    document.getElementById("profile-form").addEventListener("submit", async function(e) {
        e.preventDefault();

        const username = document.getElementById("username").value.trim();

        // validacia
        if (!username) {
            return showError("Používateľské meno nemôže byť prázdne");
        }

        if (username.length < 3) {
            return showError("Používateľské meno musí mať aspoň 3 znaky");
        }

        if (username.length > 25) {
            return showError("Používateľské meno je príliš dlhé (max 25 znakov)!");
        }

        const formData = new FormData(this);

        const success = await sendRequest("/settings/update-profile", formData);

        if (success) {
            setTimeout(() => location.reload(), 1000);
        }
    });


    //pre heslo
    document.getElementById("password-form").addEventListener("submit", async function(e) {
        e.preventDefault();

        const password = document.getElementById("new_password").value.trim();

        // validacia
        if (!password) {
            return showError("Heslo nemôže byť prázdne");
        }

        if (password.length < 5) {
            return showError("Heslo musí mať aspoň 5 znakov");
        }

        const formData = new FormData(this);

        const success = await sendRequest("/settings/update-password", formData);

        if (success) {
            setTimeout(() => location.reload(), 1000);
        }
    });


    //pre email
    document.getElementById("email-form").addEventListener("submit", async function(e) {
        e.preventDefault();

        const email = document.getElementById("email").value.trim();

        const gmailRegex = /^[a-zA-Z0-9._%+-]+@gmail\.com$/;

        if (email & !gmailRegex.test(email)) {
            return showError("Použite Gmail adresu (@gmail.com)");
        }


        const formData = new FormData(this);

        await sendRequest("/settings/update-email", formData);
    });

});


// 🔥 spoločná funkcia pre fetch
async function sendRequest(url, formData) {

    try {
        const response = await fetch(url, {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (data.success) {

            Swal.fire({
                toast: true,
                position: "top-end",
                icon: "success",
                title: data.message || "Hotovo!",
                timer: 1500,
                showConfirmButton: false
            });

            return true;

        } else {

            Swal.fire({
                toast: true,
                position: "top-end",
                icon: "error",
                title: data.message || "Chyba",
                timer: 1500,
                showConfirmButton: false
            });

            return false;
        }

    } catch (error) {

        console.error(error);

        Swal.fire({
            toast: true,
            position: "top-end",
            icon: "error",
            title: "Nepodarilo sa spojiť so serverom",
            timer: 1500,
            showConfirmButton: false
        });

        return false;
    }
}


// funckia na chybu
function showError(message) {
    Swal.fire({
        toast: true,
        position: "top-end",
        icon: "warning",
        title: message,
        timer: 1800,
        showConfirmButton: false
    });
}