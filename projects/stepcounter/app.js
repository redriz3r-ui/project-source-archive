// Check if the browser supports Geolocation
if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(showPosition, showError);
} else {
    document.getElementById("location").textContent = "Geolocation is not supported by this browser.";
}

// Function to handle successful location retrieval
function showPosition(position) {
    const userLat = position.coords.latitude;
    const userLon = position.coords.longitude;

    // Display user coordinates
    document.getElementById("location").textContent = `Your Location: Latitude ${userLat}, Longitude ${userLon}`;

    // Destination coordinates (e.g., Visalia, CA)
    const destination = { latitude: 36.3302, longitude: -119.2921 };
    
    // Calculate and display the distance
    const distance = calculateDistance(userLat, userLon, destination.latitude, destination.longitude);
    document.getElementById("distance").textContent = `Distance to Visalia, CA: ${distance.toFixed(2)} miles`;
}

// Function to calculate distance using the Haversine formula
function calculateDistance(lat1, lon1, lat2, lon2) {
    const toRadians = angle => (angle * Math.PI) / 180;

    const R = 3958.8; // Radius of Earth in miles
    const dLat = toRadians(lat2 - lat1);
    const dLon = toRadians(lon2 - lon1);

    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) *
              Math.sin(dLon / 2) * Math.sin(dLon / 2);

    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

// Function to handle errors
function showError(error) {
    switch(error.code) {
        case error.PERMISSION_DENIED:
            document.getElementById("location").textContent = "User denied the request for Geolocation.";
            break;
        case error.POSITION_UNAVAILABLE:
            document.getElementById("location").textContent = "Location information is unavailable.";
            break;
        case error.TIMEOUT:
            document.getElementById("location").textContent = "The request to get user location timed out.";
            break;
        case error.UNKNOWN_ERROR:
            document.getElementById("location").textContent = "An unknown error occurred.";
            break;
    }
}