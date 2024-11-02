// Initialize the current month and year
const today = new Date();
let currentMonth = today.getMonth();
let currentYear = today.getFullYear();
let eventsData = []; // Array to hold all events

// Function to update the month label
function updateMonthLabel(month, year) {
    const monthNames = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ];
    document.getElementById('monthLabel').textContent = `${monthNames[month]} ${year}`;
}

// Load events from localStorage on page load
function loadEvents() {
    const savedEvents = localStorage.getItem('eventsData');
    eventsData = savedEvents ? JSON.parse(savedEvents) : [];
}

// Save events to localStorage
function saveEvents() {
    localStorage.setItem('eventsData', JSON.stringify(eventsData));
}

// Function to change the month and regenerate the calendar
function changeMonth(offset) {
    currentMonth += offset;

    if (currentMonth < 0) {
        currentMonth = 11;
        currentYear -= 1;
    } else if (currentMonth > 11) {
        currentMonth = 0;
        currentYear += 1;
    }

    generateCalendar(currentMonth, currentYear);
}

// Function to add or edit an event
// Example of how to add or edit an event with an Instagram URL
function saveEvent() {
    const day = document.getElementById('saveEvent').getAttribute('data-day');
    const title = document.getElementById('eventTitle').value;
    const venue = document.getElementById('eventVenue').value;
    const hour = document.getElementById('eventHour').value;
    const minute = document.getElementById('eventMinute').value;
    const period = document.getElementById('eventPeriod').value;
    const description = document.getElementById('eventDescription').value;
    const instagramUrl = document.getElementById('eventInstagramUrl').value; // New Instagram URL input

    if (!title || !hour || !minute || !period) {
        alert("Please fill out all event fields.");
        return;
    }

    const time = `${hour}:${minute} ${period}`;
    const eventDate = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;


    // Create or update event
    const existingEventIndex = eventsData.findIndex(event => event.date === eventDate);
    const newEvent = { title, date: eventDate, time, description, instagramUrl };

    if (existingEventIndex > -1) {
        eventsData[existingEventIndex] = newEvent; // Update existing event
    } else {
        eventsData.push(newEvent); // Add new event
    }

    saveEvents(); // Save to localStorage
    closeEventModal();
    generateCalendar(currentMonth, currentYear);
    updateEventList(); // Refresh upcoming events list
}

// Delete an event
function deleteEvent() {
    const day = document.getElementById('deleteEvent').getAttribute('data-day');
    const eventDate = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;

    eventsData = eventsData.filter(event => event.date !== eventDate); // Remove the event
    saveEvents();
    closeEventModal();
    generateCalendar(currentMonth, currentYear);
    updateEventList(); // Refresh upcoming events list
}

// Function to generate the calendar for the current month
function generateCalendar(month, year) {
    updateMonthLabel(month, year);
    const calendar = document.getElementById('calendar');
    calendar.innerHTML = '';

    addDayNames(calendar);

    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const firstDay = new Date(year, month, 1).getDay();

    // Empty cells for days before the start of the month
    for (let i = 0; i < firstDay; i++) {
        const emptyDiv = document.createElement('div');
        emptyDiv.classList.add('date');
        calendar.appendChild(emptyDiv);
    }

    // Calendar days
    for (let day = 1; day <= daysInMonth; day++) {
        const eventDate = new Date(year, month, day, 12, 0, 0); // Set time to noon for consistency
        const dateStr = `${eventDate.getFullYear()}-${String(eventDate.getMonth() + 1).padStart(2, '0')}-${String(eventDate.getDate()).padStart(2, '0')}`;
        const dayDiv = document.createElement('div');
        dayDiv.classList.add('date');
        dayDiv.textContent = day;

        // Check if today's date to highlight
        if (
            day === today.getDate() &&
            month === today.getMonth() &&
            year === today.getFullYear()
        ) {
            dayDiv.classList.add('today');
        }

        // Check if there's an event for this date
        const event = eventsData.find(e => e.date === dateStr);
        if (event) {
            const eventDiv = document.createElement('div');
            eventDiv.classList.add('event');
            eventDiv.innerHTML = `<strong>${event.title}</strong><br>${event.time}<br>${event.description}`;
            dayDiv.appendChild(eventDiv);
        }

        dayDiv.addEventListener('click', () => openEventModal(day));
        calendar.appendChild(dayDiv);
    }
}

function formatDateString(dateStr) {
    const [year, month, day] = dateStr.split("-");
    const date = new Date(year, month - 1, day); // Adjust month index

    const options = { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' };
    return date.toLocaleDateString("en-US", options);
}

// Function to display events in the list below the calendar
function updateEventList() {
    const eventList = document.getElementById('eventList');
    eventList.innerHTML = ''; // Clear the existing list

    if (eventsData.length === 0) {
        // Display message when there are no events
        const noEventsMessage = document.createElement('div');
        noEventsMessage.classList.add('no-events-message'); // Add a class for styling
        noEventsMessage.textContent = "No events yet. Check back soon!";
        eventList.appendChild(noEventsMessage);
        return;
    }

    // Sort events by date and time to display upcoming events in order
    const sortedEvents = eventsData.sort((a, b) => new Date(a.date) - new Date(b.date));

    // Render each event in the upcoming events list
    sortedEvents.forEach(event => {
        const eventItem = document.createElement('div');
        eventItem.classList.add('event-item');

        // Add clickable title with Instagram URL
        eventItem.innerHTML = `
            <h3>
                <a href="${event.instagramUrl}" target="_blank" rel="noopener noreferrer">
                    ${event.title}
                </a>
            </h3>
            <p><strong>Venue:</strong> ${event.venue}</p>
            <p><strong>Date:</strong> ${formatDateString(event.date)}</p>
            <p><strong>Time:</strong> ${event.time}</p>
            <p><strong>Description:</strong> ${event.description}</p>
        `;

        eventList.appendChild(eventItem);
    });
}

// Utility functions for modal management
function openEventModal(day) {
    clearModalFields();
    document.getElementById('eventModal').style.display = 'block';
    document.getElementById('saveEvent').setAttribute('data-day', day);
    document.getElementById('deleteEvent').setAttribute('data-day', day); // Set data-day for delete button

    // Get the event date format
    const eventDate = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const event = eventsData.find(e => e.date === eventDate);

    // If an event exists, populate fields and show delete button
    if (event) {
        document.getElementById('eventTitle').value = event.title;
        document.getElementById('eventDescription').value = event.description;
        document.getElementById('eventHour').value = event.time.split(':')[0]; // Extract hour
        document.getElementById('eventMinute').value = event.time.split(':')[1].split(' ')[0]; // Extract minute
        document.getElementById('eventPeriod').value = event.time.split(' ')[1]; // Extract AM/PM
        document.getElementById('eventInstagramUrl').value = event.instagramUrl;

        document.getElementById('deleteEvent').style.display = 'block'; // Show delete button for existing event
    } else {
        document.getElementById('deleteEvent').style.display = 'none'; // Hide delete button if no event
    }
}

function closeEventModal() {
    document.getElementById('eventModal').style.display = 'none';
}

function clearModalFields() {
    document.getElementById('eventTitle').value = '';
    document.getElementById('eventDescription').value = '';
    document.getElementById('eventHour').value = '';
    document.getElementById('eventMinute').value = '';
    document.getElementById('eventPeriod').value = '';
    document.getElementById('deleteEvent').style.display = 'none';
}

// Helper function to add day names to calendar
function addDayNames(calendar) {
    const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    dayNames.forEach(day => {
        const dayDiv = document.createElement('div');
        dayDiv.classList.add('day');
        dayDiv.textContent = day;
        calendar.appendChild(dayDiv);
    });
}

// Display events as clickable boxes for ticket selection
function displayEventBoxes() {
    const eventSelection = document.getElementById('eventSelection');
    eventSelection.innerHTML = ''; // Clear any existing boxes

    eventsData.forEach((event, index) => {
        const eventBox = document.createElement('div');
        eventBox.classList.add('event-box');
        eventBox.textContent = `${event.title} - ${new Date(event.date).toDateString()}`;
        eventBox.dataset.eventIndex = index;
        eventBox.onclick = () => selectEventForTickets(index);
        eventSelection.appendChild(eventBox);
    });
}

// Show ticket quantity input when an event is selected
function selectEventForTickets(eventIndex) {
    document.getElementById('ticketQuantity').style.display = 'block';
    document.getElementById('ticketQuantity').dataset.selectedEventIndex = eventIndex;
}

// Add tickets to a simple cart list
function addTicketsToCart() {
    const selectedEventIndex = document.getElementById('ticketQuantity').dataset.selectedEventIndex;
    const ticketCount = parseInt(document.getElementById('ticketCount').value);
    if (!selectedEventIndex || !ticketCount) return;

    const event = eventsData[selectedEventIndex];
    const cartItems = document.getElementById('cartItems');

    const cartItem = document.createElement('li');
    cartItem.textContent = `${event.title} - ${ticketCount} tickets`;
    cartItems.appendChild(cartItem);

    // Show the cart if hidden
    document.getElementById('ticketCart').style.display = 'block';
}

// Simple checkout that confirms the order and clears the cart
function checkout() {
    alert("Thank you for your purchase!");
    document.getElementById('cartItems').innerHTML = ''; // Clear the cart items
    document.getElementById('ticketCart').style.display = 'none'; // Hide cart
}

// Load events and display event boxes on page load
window.addEventListener('load', () => {
    loadEvents();
    displayEventBoxes();
    updateEventList();
    generateCalendar(currentMonth, currentYear);
});

// Define the array of band names
const jazzBands = ["Band 1", "Band 2", "Band 3", "Band 4", "Band 5", "Band 6"];

// Function to display bands on the page
function displayBands() {
    const bandListContainer = document.getElementById("bandList");

    jazzBands.forEach((band, index) => {
        // Create a div for each band with clickable styling
        const bandLink = document.createElement("a");
        bandLink.href = `#${band.toLowerCase().replace(/\s+/g, '-')}`; // Make it clickable; adjust href if needed
        bandLink.className = "band-link";
        bandLink.textContent = band;

        // Append the link to the bandList container
        bandListContainer.appendChild(bandLink);
    });
}

// Call displayBands to populate the bands when the page loads
window.onload = displayBands;

// Event listeners
document.getElementById('saveEvent').addEventListener('click', saveEvent);
document.getElementById('deleteEvent').addEventListener('click', deleteEvent);
document.getElementById('prevMonth').addEventListener('click', () => changeMonth(-1));
document.getElementById('nextMonth').addEventListener('click', () => changeMonth(1));

// Initialize the calendar on page load
window.addEventListener('load', () => {
    loadEvents();
    generateCalendar(currentMonth, currentYear);
    updateEventList(); // Initial render of upcoming events list
});