const bookbtn = document.getElementById('user-book_btn');

bookbtn.addEventListener('click', () => {
    const date = new Date();
    formattedDate = `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;

    const passenger_id = document.getElementById('book-passenger_id').value;
    const ticket_id = document.getElementById('book-ticket_id').value;
    const payment_id = document.getElementById('pay-payment_id').value;
    let query;
    let payment_query;

    

    if (passenger_id !== "" || ticket_id !== "" || payment_id !== "") {

            query = `UPDATE ticket SET  
                            passenger_id = "${passenger_id}",
                            payment_id = ${payment_id},
                            date_of_booking = "${formattedDate}"
                            WHERE ticket_id = ${ticket_id} 
                            AND passenger_id is null`;

            payment_query = `insert into payment (payment_id, date, amount, method)
                             values (${payment_id}, "${formattedDate}", 200, "Credit Card");`;              
    } 
    // Update the ticket //   
    const xhr = new XMLHttpRequest();
    xhr.open('POST', 'http://localhost:3306/insert', true);
    xhr.setRequestHeader('Content-Type', 'application/json');

    xhr.onreadystatechange = function() {
        if (xhr.readyState === XMLHttpRequest.DONE) {
            if (xhr.status === 200) {
                console.log('Ticket successfully was booked');
            } else {
                console.error('Error');
            }
        }
    };
    const data = JSON.stringify({ Query: query });
    xhr.send(data);


    // Update the payment //

    const newxhr = new XMLHttpRequest();
    newxhr.open('POST', 'http://localhost:3306/insert', true);
    newxhr.setRequestHeader('Content-Type', 'application/json');

    newxhr.onreadystatechange = function() {
        if (newxhr.readyState === XMLHttpRequest.DONE) {
            if (newxhr.status === 200) {
                console.log('Payment method wass successfully saved');
            } else {
                console.error('Error');
            }
        }
    };
    const payment_data = JSON.stringify({ Query: payment_query});
    newxhr.send(payment_data);

});

