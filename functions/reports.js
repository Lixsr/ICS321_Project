const reportsBtn = document.getElementById('admin-reports_btn');
const getPcgBtn = document.getElementById('get-pcg');
const waitlistBtn = document.getElementById('get-waitlisted_btn');

getPcgBtn.addEventListener('click', bookingPcg);
waitlistBtn.addEventListener('click', getWaitlist);
reportsBtn.addEventListener('click', () => {
    activeFlights();
    payments();
    cancelledTickets();
    getLoadFactor();

});



function getLoadFactor(){
    const loadFactorDiv = document.getElementById('load-factor_container');
    
    const query = `SELECT p.registration_number, COALESCE(SUM(ast.number_of_seats), 0) AS total_seats,
                    COALESCE(SUM(CASE WHEN t.status = 'active' THEN 1 ELSE 0 END), 0) AS booked_seats 
                    FROM plane p LEFT JOIN flight f ON p.registration_number = f.plane_id 
                    LEFT JOIN ticket t ON f.flight_number = t.flight_number LEFT JOIN 
                    aircraft_seatstype ast ON p.aircraft_id = ast.aircraft_id 
                    GROUP BY p.registration_number;`;
    fetch('http://localhost:3306/select', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ Query: query }),
    })
        .then(response => response.json())
        .then(data => {
            loadFactorDiv.innerHTML = "";
            data.forEach(e => {
                const lf = e.booked_seats / e.total_seats * 100;
                const divEl = document.createElement('div');
                divEl.classList.add('load-factor');
                divEl.innerHTML = `<p> ${e.registration_number}: ${numForamat(lf)}%</p>`;
                loadFactorDiv.appendChild(divEl);
            });
        })
        .catch(error => {
            console.error(`Error: ${error}`);
        });
}


function numForamat(number) {
    return parseInt(number.toString().slice(0, 2), 10);
}


// Generates the active flights //
function activeFlights() {
    const activeFlightsDiv = document.querySelector('#active-flights');
    
    const query = `SELECT flight_number FROM ticket WHERE status = "active";`;
    fetch('http://localhost:3306/select', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ Query: query }),
    })
        .then(response => response.json())
        .then(data => {
            activeFlightsDiv.innerHTML = "";
            const addedFlightNumbers = new Set();
            data.forEach(e => {
                if (!addedFlightNumbers.has(e.flight_number)) {
                    const divEl = document.createElement('div');
                    divEl.classList.add('active-flight');
                    divEl.innerHTML = `<small>Flight ID: ${e.flight_number}</small>`;
                    activeFlightsDiv.appendChild(divEl);
                    addedFlightNumbers.add(e.flight_number);
                }
            });
        })
        .catch(error => {
            console.error(`Error: ${error}`);
        });
}

// show all completed payments //
function payments() {
    const paymentsDiv = document.querySelector('#payments');
    
    const query = `SELECT * FROM payment;`;
    fetch('http://localhost:3306/select', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ Query: query }),
    })
        .then(response => response.json())
        .then(data => {
            paymentsDiv.innerHTML = "";
            data.forEach(e => {
                const divEl = document.createElement('div');
                divEl.classList.add('payment');
                divEl.innerHTML = `
                                    <p>Transaction ID: ${e.transaction_id}</p>
                                    <p>Amount: ${e.amount}</p>
                                    <p>method: ${e.method}</p>
                                    <p>Date: ${e.date}</p>`;
                paymentsDiv.appendChild(divEl);
            
            });
        })
        .catch(error => {
            console.error(`Error: ${error}`);
        });
}

// show all cancelled tickets //
function cancelledTickets() {
    const cancelledTicketsDiv = document.querySelector('#cancelled-tickets');
    
    const query = `SELECT * FROM ticket WHERE status = "cancelled";`;
    fetch('http://localhost:3306/select', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ Query: query }),
    })
        .then(response => response.json())
        .then(data => {
            cancelledTicketsDiv.innerHTML = "";
            data.forEach(e => {
                const divEl = document.createElement('div');
                divEl.classList.add('cancelled-ticket');
                divEl.innerHTML = `<p>Ticket ID: ${e.ticket_id}</p>`;
                cancelledTicketsDiv.appendChild(divEl);
            });
        })
        .catch(error => {
            console.error(`Error: ${error}`);
        });
}

function dateFormat(date){
    const formattedDate = new Date(date);
    const year = formattedDate.getFullYear();
    const month = String(formattedDate.getMonth() + 1).padStart(2, '0');
    const day = String(formattedDate.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function getWaitlist(){
    const flight_id = document.getElementById('waitlisted-flight_id').value;
    const waitlistedDiv = document.getElementById('class-waitlisted_container');

    const query = `SELECT s1.flight_id, COUNT(s1.seat_type) AS count,
                 seat_type, t1.passenger_id FROM seat s1 
                 JOIN ticket t1 ON s1.flight_id = t1.flight_number 
                 WHERE t1.status = 'waitlisted' AND s1.flight_id = "${flight_id}"
                 GROUP BY t1.flight_number;`;

    fetch('http://localhost:3306/select', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ Query: query }),
    })
        .then(response => response.json())
        .then(data => {
            waitlistedDiv.innerHTML = "";
            data.forEach(e => {
                const divEl = document.createElement('div');
                divEl.classList.add('waitlisted');
                divEl.innerHTML = `<p>${e.seat_type}: ${e.passenger_id}</p>`;
                waitlistedDiv.appendChild(divEl);
            });
        })
        .catch(error => {
            console.error(`Error: ${error}`);
        });
}


function bookingPcg(){
    const pcgDate = document.getElementById('pcg-date').value;
    const bookingPcgDiv = document.getElementById('booking-pcg_container');

    const query = `SELECT t1.flight_number, COUNT(t2.status) AS count
                    FROM flight t1
                    JOIN ticket t2 ON t1.flight_number = t2.flight_number
                    WHERE t2.status = 'active' AND t1.date = "${dateFormat(pcgDate)}"
                    GROUP BY t2.flight_number;`;

    fetch('http://localhost:3306/select', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ Query: query }),
    })
        .then(response => response.json())
        .then(data => {
            bookingPcgDiv.innerHTML = "";
            data.forEach(e => {
                const divEl = document.createElement('div');
                divEl.classList.add('payment');
                divEl.innerHTML = `<p>ID: ${e.flight_number}</p>
                                   <p>Occupied PCG: ${e.count/20 * 100}%</p>`;
                bookingPcgDiv.appendChild(divEl);
            
            });
        })
        .catch(error => {
            console.error(`Error: ${error}`);
        });
}


