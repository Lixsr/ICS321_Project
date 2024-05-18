const insertBtn = document.getElementById('insertBtn');
const removeBtn = document.getElementById('removeBtn');
const updateBtn = document.getElementById('updateBtn');

insertBtn.addEventListener('click', () => {
    const ticket_id = document.getElementById('insert-ticket_id').value;
    const seat_numer = document.getElementById('insert-seat_number').value;
    const flight_number = document.getElementById('insert-flight_number').value;
    
    const query = `INSERT INTO ticket (ticket_id, seat_number, flight_number, status) 
            VALUES (${ticket_id}, "${seat_numer}", "${flight_number}", "active");`;
    const xhr = new XMLHttpRequest();
    xhr.open('POST', 'http://localhost:3306/insert', true);
    xhr.setRequestHeader('Content-Type', 'application/json');

    xhr.onreadystatechange = function() {
        if (xhr.readyState === XMLHttpRequest.DONE) {
            if (xhr.status === 200) {
                console.log('Data inserted successfully');
            } else {
                console.error('Error inserting data');
            }
        }
    };
    const data = JSON.stringify({ Query: query });
    xhr.send(data);
});
removeBtn.addEventListener('click', () =>{
    const ticket_id = document.getElementById('remove-ticket_id').value;
    query = `DELETE FROM ticket WHERE ticket_ID = ${ticket_id}`;
    const xhr = new XMLHttpRequest();
    xhr.open('POST', 'http://localhost:3306/insert', true);
    xhr.setRequestHeader('Content-Type', 'application/json');

    xhr.onreadystatechange = function() {
        if (xhr.readyState === XMLHttpRequest.DONE) {
            if (xhr.status === 200) {
                console.log('Data deleted successfully');
            } else {
                console.error('Error deleteing data');
            }
        }
    };
    const data = JSON.stringify({ Query: query });
    xhr.send(data);
});

updateBtn.addEventListener('click', () =>{
    const ticket_id = document.getElementById('update-ticket_id').value;
    const seat_number = document.getElementById('update-seat_number').value;
    const flight_number = document.getElementById('update-flight_number').value;
    const status = document.getElementById('update-status').value;
    let query = `UPDATE ticket SET `;
    const updates = [];

    if (seat_number !== "") {
        updates.push(`seat_number = "${seat_number}"`);
    }
    if (flight_number !== "") {
        console.log(dateFormat(flight_number))
        updates.push(`flight_number = "${flight_number}"`);
    }
    
    if (status !== "") {
        updates.push(`status = "${status}"`);
    }
    
    query += updates.join(', ');
    query += ` WHERE ticket_id = ${ticket_id};`;
    
    const xhr = new XMLHttpRequest();
    xhr.open('POST', 'http://localhost:3306/insert', true);
    xhr.setRequestHeader('Content-Type', 'application/json');

    xhr.onreadystatechange = function() {
        if (xhr.readyState === XMLHttpRequest.DONE) {
            if (xhr.status === 200) {
                console.log('Data deleted successfully');
            } else {
                console.error('Error deleteing data');
            }
        }
    };
    const data = JSON.stringify({ Query: query });
    xhr.send(data);
});










