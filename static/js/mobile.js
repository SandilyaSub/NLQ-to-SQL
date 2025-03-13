// Mobile-specific JavaScript functionality

document.addEventListener('DOMContentLoaded', function() {
    // Only run on mobile devices
    if (window.innerWidth <= 767) {
        initializeMobileView();
    }
    
    // Listen for window resize events to handle orientation changes
    window.addEventListener('resize', function() {
        if (window.innerWidth <= 767) {
            initializeMobileView();
        } else {
            // Reset any mobile-specific changes if switching to desktop
            resetToDesktopView();
        }
    });
});

function initializeMobileView() {
    // Create sidebar toggle button if it doesn't exist
    if (!document.querySelector('.sidebar-toggle')) {
        const toggleButton = document.createElement('div');
        toggleButton.className = 'sidebar-toggle';
        toggleButton.innerHTML = '<i class="fas fa-bars"></i>';
        document.body.appendChild(toggleButton);
        
        // Add click event to toggle sidebar
        toggleButton.addEventListener('click', function() {
            const sidebar = document.querySelector('.app-sidebar');
            sidebar.classList.toggle('expanded');
            
            // Change icon based on state
            const icon = this.querySelector('i');
            if (sidebar.classList.contains('expanded')) {
                icon.className = 'fas fa-times';
            } else {
                icon.className = 'fas fa-bars';
            }
        });
    }
    
    // Create collapsible headers for history and logs
    createCollapsibleSection('Query History', 'history-container');
    createCollapsibleSection('Processing Logs', 'logs-container');
}

function createCollapsibleSection(title, containerClass) {
    const container = document.querySelector('.' + containerClass);
    
    // Skip if already processed
    if (container.querySelector('.collapsible-header')) return;
    
    // Get the original h2 and hide it
    const originalTitle = container.querySelector('h2');
    if (originalTitle) originalTitle.style.display = 'none';
    
    // Create collapsible header
    const header = document.createElement('div');
    header.className = 'collapsible-header';
    header.innerHTML = `
        <span>${title}</span>
        <i class="fas fa-chevron-down"></i>
    `;
    
    // Insert header at the beginning of container
    container.insertBefore(header, container.firstChild);
    
    // Add click event
    header.addEventListener('click', function() {
        container.classList.toggle('expanded');
        
        // Change icon based on state
        const icon = this.querySelector('i');
        if (container.classList.contains('expanded')) {
            icon.className = 'fas fa-chevron-up';
        } else {
            icon.className = 'fas fa-chevron-down';
        }
    });
}

function resetToDesktopView() {
    // Remove sidebar toggle button
    const toggleButton = document.querySelector('.sidebar-toggle');
    if (toggleButton) {
        toggleButton.remove();
    }
    
    // Reset sidebar
    const sidebar = document.querySelector('.app-sidebar');
    if (sidebar) {
        sidebar.classList.remove('expanded');
    }
    
    // Show original titles
    document.querySelectorAll('.history-container h2, .logs-container h2').forEach(el => {
        el.style.display = '';
    });
    
    // Reset containers
    document.querySelectorAll('.history-container, .logs-container').forEach(container => {
        container.classList.remove('expanded');
    });
}
