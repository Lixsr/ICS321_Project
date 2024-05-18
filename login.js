document.getElementById('loginButton').addEventListener('click', () => {
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const loginType = document.getElementById('login-type');

    // Example: check if username and password are not empty
    let query;
    let dist;
    if (loginType.checked){
        query = `SELECT * FROM admin;`;
        dist = 'admin.html'
    }else {
        query = `SELECT * FROM person;`;
        dist = 'user.html'
    }
    

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
            if (username.trim() === e.username && password.trim() === e.password) {
                window.location.href = dist;
            }
        });
        
    })
    .catch(error => {
        console.error(`Error: ${error}`);
    });
    
    
});


