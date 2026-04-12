/* Recipe Site — minimal custom JS */
/* Alpine.js and HTMX handle all interactivity.
   This file exists as a hook for any future enhancements. */

document.addEventListener('DOMContentLoaded', function () {
    // Close detail overlay on Escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            // Dispatch a custom event that Alpine.js can listen to
            document.dispatchEvent(new CustomEvent('close-recipe-detail'));
        }
    });
});
