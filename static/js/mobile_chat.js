// Mobile Chat Interface JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const chatMessages = document.getElementById('chat-messages');
    const queryForm = document.getElementById('query-form');
    const queryInput = document.getElementById('query-input');
    const userMessageTemplate = document.getElementById('user-message-template');
    const systemMessageTemplate = document.getElementById('system-message-template');
    const welcomeMessage = document.querySelector('.system-message');
    let isFirstQuery = true;
    
    // Initialize the chat interface
    initChatInterface();
    
    // Handle form submission
    queryForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const query = queryInput.value.trim();
        if (query) {
            // If this is the first query, shrink the welcome message
            if (isFirstQuery) {
                welcomeMessage.classList.add('welcome-collapsed');
                isFirstQuery = false;
            }
            
            sendQuery(query);
            queryInput.value = '';
        }
    });
    
    // Initialize chat interface
    function initChatInterface() {
        // Add event listeners for section toggles
        chatMessages.addEventListener('click', function(e) {
            const sectionHeader = e.target.closest('.section-header');
            if (sectionHeader) {
                toggleSection(sectionHeader);
            }
            
            // Handle feedback buttons
            const feedbackBtn = e.target.closest('.feedback-btn');
            if (feedbackBtn) {
                handleFeedback(feedbackBtn);
            }
            
            // Handle welcome message expansion/collapse
            if (e.target.closest('.welcome-collapsed')) {
                e.target.closest('.welcome-collapsed').classList.toggle('welcome-expanded');
            }
        });
        
        // Scroll to bottom on load
        scrollToBottom();
    }
    
    // Send a query to the server
    function sendQuery(query) {
        // Add user message to chat
        addUserMessage(query);
        
        // Add system message with thinking indicator
        const systemMessage = addSystemMessage();
        const thinkingIndicator = systemMessage.querySelector('.thinking');
        const responseSections = systemMessage.querySelector('.response-sections');
        
        // Show thinking indicator
        thinkingIndicator.classList.remove('hidden');
        responseSections.classList.add('hidden');
        
        // Scroll to bottom
        scrollToBottom();
        
        // Send query to server
        fetch('/api/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ question: query })
        })
        .then(response => response.json())
        .then(data => {
            // Hide thinking indicator
            thinkingIndicator.classList.add('hidden');
            responseSections.classList.remove('hidden');
            
            // Debug log the entire response to see its structure
            console.log('API Response Data:', JSON.stringify(data));
            
            // Update system message with response
            updateSystemMessage(systemMessage, data);
            
            // Highlight code blocks
            hljs.highlightAll();
            
            // Scroll to bottom
            scrollToBottom();
        })
        .catch(error => {
            console.error('Error:', error);
            // Hide thinking indicator
            thinkingIndicator.classList.add('hidden');
            
            // Show error message
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            errorDiv.textContent = 'Sorry, there was an error processing your query. Please try again.';
            systemMessage.querySelector('.message-content').appendChild(errorDiv);
            
            // Scroll to bottom
            scrollToBottom();
        });
    }
    
    // Add user message to chat
    function addUserMessage(query) {
        const messageClone = userMessageTemplate.content.cloneNode(true);
        messageClone.querySelector('.query-text').textContent = query;
        chatMessages.appendChild(messageClone);
    }
    
    // Add system message to chat
    function addSystemMessage() {
        const messageClone = systemMessageTemplate.content.cloneNode(true);
        chatMessages.appendChild(messageClone);
        return chatMessages.lastElementChild;
    }
    
    // Update system message with response
    function updateSystemMessage(systemMessage, data) {
        // Debug log the entire response to see its structure
        console.log('API Response Data:', JSON.stringify(data));
        
        // Update SQL query - check multiple possible property names
        const sqlCode = systemMessage.querySelector('code.sql');
        
        // Check for SQL in the response with various possible property names
        // First, check if data exists and is not null
        if (!data) {
            console.error('Response data is null or undefined');
            sqlCode.textContent = 'No SQL query generated - No data received';
            return;
        }
        
        // Try to find SQL query in the response using various property names
        let sqlQuery = null;
        
        if (typeof data.sql !== 'undefined' && data.sql !== null) {
            console.log('Found SQL in data.sql:', data.sql);
            sqlQuery = data.sql;
        } else if (typeof data.generated_sql !== 'undefined' && data.generated_sql !== null) {
            console.log('Found SQL in data.generated_sql:', data.generated_sql);
            sqlQuery = data.generated_sql;
        } else if (typeof data.query !== 'undefined' && data.query !== null) {
            console.log('Found SQL in data.query:', data.query);
            sqlQuery = data.query;
        } else {
            console.error('No SQL query found in response data with known property names');
        }
        
        // Set the SQL code content
        if (sqlQuery) {
            sqlCode.textContent = sqlQuery;
        } else {
            sqlCode.textContent = 'No SQL query generated';
        }
        
        // Update results
        const resultsContent = systemMessage.querySelector('.results-content');
        
        if (data.error) {
            // Show error message
            resultsContent.innerHTML = `<div class="error-message">${data.error}</div>`;
        } else if (data.results && data.results.length > 0) {
            // Create table for results
            const table = document.createElement('table');
            table.className = 'results-table';
            
            // Create table header
            const thead = document.createElement('thead');
            const headerRow = document.createElement('tr');
            
            // Get column names from first result
            const columns = Object.keys(data.results[0]);
            
            columns.forEach(column => {
                const th = document.createElement('th');
                th.textContent = column;
                headerRow.appendChild(th);
            });
            
            thead.appendChild(headerRow);
            table.appendChild(thead);
            
            // Create table body
            const tbody = document.createElement('tbody');
            
            data.results.forEach(result => {
                const row = document.createElement('tr');
                
                columns.forEach(column => {
                    const td = document.createElement('td');
                    td.textContent = result[column] !== null ? result[column] : 'NULL';
                    row.appendChild(td);
                });
                
                tbody.appendChild(row);
            });
            
            table.appendChild(tbody);
            resultsContent.innerHTML = '';
            resultsContent.appendChild(table);
            
            // Add execution time if available
            if (data.nlq_duration || data.sql_duration) {
                const timingInfo = document.createElement('div');
                timingInfo.className = 'timing-info';
                
                if (data.nlq_duration) {
                    timingInfo.innerHTML += `<div>NLQ to SQL: ${data.nlq_duration.toFixed(2)}s</div>`;
                }
                
                if (data.sql_duration) {
                    timingInfo.innerHTML += `<div>SQL Execution: ${data.sql_duration.toFixed(2)}s</div>`;
                }
                
                resultsContent.appendChild(timingInfo);
            }
        } else {
            // No results
            resultsContent.innerHTML = '<div class="no-results">No results found</div>';
        }
    }
    
    // Toggle section visibility
    function toggleSection(sectionHeader) {
        const section = sectionHeader.closest('.response-section');
        const content = section.querySelector('.section-content');
        const icon = sectionHeader.querySelector('i');
        
        // Toggle active class on header
        sectionHeader.classList.toggle('active');
        
        // Toggle show class on content
        content.classList.toggle('show');
        
        // Update icon
        if (content.classList.contains('show')) {
            icon.className = 'fas fa-chevron-up';
        } else {
            icon.className = 'fas fa-chevron-down';
        }
    }
    
    // Handle feedback button clicks
    function handleFeedback(button) {
        const feedback = button.getAttribute('data-feedback');
        const feedbackSection = button.closest('.feedback');
        const buttons = feedbackSection.querySelectorAll('.feedback-btn');
        
        // Remove selected class from all buttons
        buttons.forEach(btn => btn.classList.remove('selected'));
        
        // Add selected class to clicked button
        button.classList.add('selected');
        
        // Send feedback to server
        const messageElement = button.closest('.message');
        const messageIndex = Array.from(chatMessages.children).indexOf(messageElement);
        
        fetch('/api/feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query_id: messageIndex,
                feedback: feedback === 'positive' ? 'thumbs_up' : 'thumbs_down'
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Feedback sent:', data);
        })
        .catch(error => {
            console.error('Error sending feedback:', error);
        });
    }
    
    // Scroll chat to bottom
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
});
