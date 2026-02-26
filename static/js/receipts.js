function deleteReceipt(receiptId){
    if (!confirm("Noazaj chcete odstrániť tento bloček?")){
        return;
    }
    
    //posleme http request na flask server
    fetch(`/delete_receipt/${receiptId}`, 
        {method: 'DELETE'})

    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document
            .getElementById(`receipt-${receiptId}`)
            .remove();
        }
    })
    .catch(error => console.error("Chyba:", error))
}

function showDetails(receiptId){
    alert("ukazujem detaily" + receiptId)
}