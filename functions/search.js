const flightsDiv = document.getElementById('search-flights');
const toggleBtn = document.getElementById('search-flights_btn');
displayFlights();

toggleBtn.addEventListener('click', () => {
    if (flightsDiv.classList.contains('hidden')){
        flightsDiv.classList.remove('hidden');
        toggleBtn.innerHTML = 'Hide';
        flightsDiv.scrollIntoView({ behavior: 'smooth' });

    }
    else {
        flightsDiv.classList.add('hidden');
        toggleBtn.innerHTML = 'Search';
    };
})

function displayFlights(){
    const query = `SELECT 
    flight_number, 
    departure_city, 
    destination_city, 
    date, 
    time 
    FROM flight;`;
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
            const divEl = document.createElement('div');
            divEl.classList.add('container');
            divEl.classList.add('flight-info');
            divEl.innerHTML = `<p>Flight Number: <small class="search-flight_number" id="search-flight_number">${e.flight_number}</small></p>
            <p>From: <small class="search-departure_city" id="search-departure_city">${e.departure_city}</small></p>
            <p>To: <small class="search-destination_city" id="search-destination_city">${e.destination_city}</small></p>
            <p>date: <small class="search-date" id="search-date">${e.date}</small></p>
            <p>time: <small class="search-time" id="search-time">${e.time}</small></p>`;
            flightsDiv.appendChild(divEl);
        });
        
    })
    .catch(error => {
        console.error(`Error: ${error}`);
    });
}
