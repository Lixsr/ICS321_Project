const promoteBtn = document.getElementById('admin-promote_btn');

promoteBtn.addEventListener('click', () => {
    const ticket_id = document.getElementById('promote-ticket_id').value;
    const query = `UPDATE ticket SET status = "active"
                    WHERE ticket_id = "${ticket_id}";`;
    

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
});