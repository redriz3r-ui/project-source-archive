const express = require('express');
const fs = require('fs');
const path = require('path');
const app = express();
const PORT = 3000;

// Middleware to serve static files
app.use(express.static('public'));

// Middleware to parse JSON data
app.use(express.json());


// Route to get the list of events
app.get('/api/events', (req, res) => {
    const eventsFilePath = path.join(__dirname, 'data', 'events.json');
    fs.readFile(eventsFilePath, 'utf-8', (err, data) => {
        if (err) {
            res.status(500).send('Error reading events data.');
        } else {
            res.json(JSON.parse(data));
        }
    });
});

// Start the server
app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});