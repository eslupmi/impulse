// Utility functions for URL handling

// Get the base URL with HTTP prefix if it exists
function getBaseUrl() {
    const currentPath = window.location.pathname;
    
    // Extract the prefix by removing the last segment (usually empty or the current page)
    const pathSegments = currentPath.split('/').filter(segment => segment !== '');
    
    // If we're on a page like /impulse/, the prefix is /impulse
    // If we're on a page like /impulse/index.html, the prefix is still /impulse
    // If we're on /, there's no prefix
    if (pathSegments.length > 0) {
        // Check if the last segment looks like a file (has extension) or is empty
        const lastSegment = pathSegments[pathSegments.length - 1];
        if (lastSegment.includes('.') || lastSegment === '') {
            // Remove the last segment if it's a file or empty
            pathSegments.pop();
        }
    }
    
    return pathSegments.length > 0 ? '/' + pathSegments.join('/') : '';
}

// Export for use in other modules
export { getBaseUrl };
