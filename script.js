insertBtn = document.getElementById('insertBtn');

insertBtn.addEventListener('click', () => {
    const id = document.getElementById('Id').value.trim();
    const name = document.getElementById('name').value.trim();
    const query = `INSERT INTO Customer (ID, Name) VALUES (${id}, "${name}");`;
    
    const xhr = new XMLHttpRequest();
    xhr.open('POST', 'http://localhost:3306/submit', true);
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