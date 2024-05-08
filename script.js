const insertBtn = document.getElementById('insertBtn');
const selectBtn = document.getElementById('selectBtn');


insertBtn.addEventListener('click', () => {
    const id = document.getElementById('Id').value.trim();
    const name = document.getElementById('name').value.trim();
    const query = `INSERT INTO Customer (ID, Name) VALUES (${id}, "${name}");`;
    
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

selectBtn.addEventListener('click', () => {
    const query = `SELECT * FROM Customer;`;
    
    fetch('http://localhost:3306/select', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ Query: query }),
    })
    .then(response => response.json())
    .then(data => {
        data.forEach(e => {
            console.log(`| ${e.ID} | ${e.Name} |`);
        });
        
    })
    .catch(error => {
        console.error(`Error: ${error}`);
    });
    
});