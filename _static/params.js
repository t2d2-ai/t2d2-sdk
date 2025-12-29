// Add class to Parameters dd elements that don't have ul.simple
document.addEventListener('DOMContentLoaded', function() {
    // Find all Parameters sections
    const paramSections = document.querySelectorAll('.field-list dt.field-odd:first-child');
    
    paramSections.forEach(function(dt) {
        if (dt.textContent.trim().includes('Parameters')) {
            const dd = dt.nextElementSibling;
            if (dd && dd.tagName === 'DD' && !dd.querySelector('ul.simple')) {
                // This dd contains a single parameter (p tag, no ul)
                dd.classList.add('single-param');
            }
        }
    });
});

