/* funckia na prepianie medzi manual a pdf formularom*/
function switchAuth(option){

    const signin = document.getElementById("signin-option")
    const register = document.getElementById("registration-option")

    if (option == "signin"){
        signin.classList.add("active")
        register.classList.remove("active")
    }
    
    else {
        register.classList.add("active")
        signin.classList.remove("active")
    }
}
