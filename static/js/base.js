async function logout(event){

    event.preventDefault();

    //popup pomocou kniznice
    const result = await Swal.fire({
        title: "Chcete sa odhásiť?",
        icon: "warning",     
        showCancelButton: true,
        confirmButtonText: "Áno, odhlásiť",
        cancelButtonText: "Zrušiť",
        confirmButtonColor: "#e74c3c",
        cancelButtonColor: "#aaa",
    });
    
    if (!result.isConfirmed){
        return;
    }

    window.location.href = '/logout';
}