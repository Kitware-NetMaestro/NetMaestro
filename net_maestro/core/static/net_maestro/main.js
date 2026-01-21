/**
 * Main JavaScript file for NetMaestro application.
 * Handles Alpine.js store initialization and utility functions.
 */

// Initialize Alpine.js global store
document.addEventListener('alpine:init', () => {
    // loadTick: incremented when "Load Data" is clicked to trigger plot updates
    Alpine.store('nm', { loadTick: 0 });
});

/**
 * Get a cookie value by name.
 * 
 * Django requires CSRF tokens for state-changing requests (POST, PUT, DELETE).
 * This function extracts the token from the cookie so it can be included in the
 * X-CSRFToken header when making AJAX requests.
 * 
 * @param {string} name - The name of the cookie to retrieve
 * @returns {string|null} The cookie value, or null if not found
 */
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
        return parts.pop().split(';').shift();
    }
    return null;
}
