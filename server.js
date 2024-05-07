const express = require('express');
const mysql = require('mysql');
const bodyParser = require('body-parser');

const app = express();

const port = 3306;

// bodyParser.json() for button, bodyParser.urlencoded({ extended: true } for form) //
app.use(bodyParser.json(), bodyParser.urlencoded({ extended: true }));

// To access the data //
const connection = mysql.createConnection({
    host: "srv1368.hstgr.io",
    user: "u662969350_admin",
    password: "P2ics321",
    database: "u662969350_Flights"
});

connection.connect();

// To allow access using button. Note: you can use form without this. //
app.use((req, res, next) => {
    res.setHeader('Access-Control-Allow-Origin', 'http://127.0.0.1:5500');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
    next();
});

// To set the server-side page //
app.get('/', (req, res) => {
    res.send('Hello World!');
});

// to insert the data using form/button. //
app.post('/submit', (req, res) => {

  // Query must match that same identifier that was given though script.js//
  // Query != query //
  const { Query } = req.body;  
  connection.query(Query, (err, result) => {
    if (err) console.log(err);
    res.send('Data inserted successfully');
  });
});

// Listen to coming requests. //
app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});

//Notes: 
// You need to run the server first using node server.js//
// To run/stop the server permenantly you can use pm2 start server.js | pm2 stop server.js // 
