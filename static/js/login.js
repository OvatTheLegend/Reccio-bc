/* funckia na prepianie medzi manual a pdf formularom*/
function switchAuth(option){

    const signin = document.getElementById("signin-option")
    const register = document.getElementById("registration-option")


    const buttons = document.querySelectorAll(".auth-switch-btn")
    
    if (option == "signin"){
        signin.classList.add("active")
        register.classList.remove("active")
    }
    
    else {
        register.classList.add("active")
        signin.classList.remove("active")
    }

    buttons.forEach(btn => {
        btn.classList.remove("active")

        if (btn.dataset.type === option) {
            btn.classList.add("active")
        }
    })
}

function validataSignin(){
    //ziskame udaje
    const username = document.querySelector('input[name="username_signin"]').value.trim();
    const password = document.querySelector('input[name="password_signin"]').value.trim();

    //zvalidujeme
    if (!username || !password) {
        Swal.fire({ 
            icon: 'warning',
            title: 'Vyplňte všetky polia.' 
        });
        return false;
    }

    return true;

}

function validateRegister(){
    //ziskame hodnoty
    const username = document.querySelector('input[name="username_register"]').value.trim();
    const password = document.querySelector('input[name="password_register"]').value.trim();
    const passwordRepeat = document.querySelector('input[name="password_repeat_register"]').value.trim();

    //teraz zvalidujemee
    if (!username || !password || !passwordRepeat) {
        Swal.fire({ 
            icon: 'warning', 
            title: 'Vyplňte všetky polia.' 
        });
        return false;
    }

    //teraz konkretne
    //meno pod 3
    if (username.length < 3) {
        Swal.fire({ icon: 'warning',
            title: 'Zvoľte dlhšie meno', 
            text: 'Minimálne 3 znaky' });
        return false;
    }

    //meno nad 25
    if (username.length > 25) {
        Swal.fire({ icon: 'warning',
            title: 'Zvoľte kratšie meno', 
            text: 'Maximálne 25 znakov'});
        return false;
    }

    //teraz kontrola hesla
    if (password.length < 5) {
        Swal.fire({ icon: 'warning', title: 'Heslo je príliš krátke', text: 'Minimálne 5 znakov' });
        return false;
    }

    //ci sa rovnaju
    if (password !== passwordRepeat) {
        Swal.fire({ icon: 'warning', title: 'Heslá sa nezhodujú' });
        return false;
    }

    //ak vsetko preslo, odosleme
    return true
}