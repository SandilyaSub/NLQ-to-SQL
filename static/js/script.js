document.addEventListener('DOMContentLoaded', function() {

    const queryInput = document.getElementById('query-input');
    const submitBtn = document.getElementById('submit-btn');
    const resultsHistory = document.getElementById('results-history');
    const logsContainer = document.getElementById('logs-container');
    const historyList = document.getElementById('history-list');
    const queryResultTemplate = document.getElementById('query-result-template');

    // Helper Functions
    function clearContainer(container) {
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }
    }

    // Function to auto-resize the input field based on content
    function autoResizeInput() {
        queryInput.style.height = 'auto';
        queryInput.style.height = queryInput.scrollHeight + 'px';
    }

    // Add event listener for submit button
    if (submitBtn) {
        submitBtn.addEventListener('click', submitQuery);
    }

    // Add event listener for Enter key
    if (queryInput) {
        queryInput.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                submitQuery();
            } else {
                setTimeout(autoResizeInput, 0);
            }
        });

        // Add event listener for input changes to handle paste events
        queryInput.addEventListener('input', autoResizeInput);
    }

    // Add event listener for history items
    if (historyList) {
        historyList.addEventListener('click', function(event) {
            if (event.target.classList.contains('history-item')) {
                queryInput.value = event.target.textContent;
                queryInput.focus();
            }
        });
    }

    // Function to submit query
    function submitQuery() {
        const question = queryInput.value.trim();
        if (!question) return;

        // Clear input
        queryInput.value = '';
        autoResizeInput(); // Reset input height after clearing

        // Add loading indicator
        const loadingIndicator = document.createElement('div');
        loadingIndicator.classList.add('loading');
        submitBtn.appendChild(loadingIndicator);
        submitBtn.disabled = true;

        // Add log entry
        addLogEntry(`Processing query: "${question}"`, 'info');

        // Send query to server
        fetch('/api/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ question })
        })
        .then(response => response.json())
        .then(data => {
            // Remove loading indicator
            if (submitBtn.contains(loadingIndicator)) {
                submitBtn.removeChild(loadingIndicator);
            }
            submitBtn.disabled = false;

            // Update history
            updateHistory(data.query_history);
            
            // Handle error
            if (data.error) {
                addLogEntry(`Error: ${data.error}`, 'error');
                
                // Even with errors, display the result container with error info
                // This ensures failed queries are visible in the history
                displayResults({
                    question: question,
                    error: data.error,
                    sql_query: data.sql_query || "",
                    results: [],
                    confidence: 0,
                    interaction_logs: [],
                    query_id: data.query_id
                });
                
                return;
            }

            // Add log entries
            addLogEntry(`Generated SQL query: ${data.sql_query}`, 'info');
            addLogEntry('Executing SQL query...', 'info');
            // Display results
            displayResults(data);
            addLogEntry('Query execution completed', 'success');
        })
        .catch(error => {
            // Remove loading indicator
            if (submitBtn.contains(loadingIndicator)) {
                submitBtn.removeChild(loadingIndicator);
            }
            submitBtn.disabled = false;
            // Add error log
            addLogEntry(`Error: ${error.message}`, 'error');
        });
    }

    // Function to create a new result container from template
    function createResultContainer(data) {
        // Clone the template
        const template = queryResultTemplate.content.cloneNode(true);
        const container = template.querySelector('.query-result');
        
        // Set question text
        const questionContent = container.querySelector('.question-content');
        questionContent.textContent = data.question;
        
        // Create preview for question section
        const questionHeader = container.querySelector('[data-section="question"]');
        const questionLines = data.question.split('\n');
        const firstLine = questionLines[0];
        const previewText = firstLine + (questionLines.length > 1 ? ' ...' : '');
        
        // Update question header to show preview
        const questionTitle = questionHeader.querySelector('.query-section-title');
        questionTitle.innerHTML = `<i class="fas fa-question-circle"></i> Question: <span class="preview-text">${previewText}</span>`;
        
        // Set SQL query
        const sqlContent = container.querySelector('.sql-content code');
        sqlContent.textContent = data.sql_query || data.sql || '';
        
        // Create preview for SQL section
        const sqlHeader = container.querySelector('[data-section="sql"]');
        const sqlTitle = sqlHeader.querySelector('.query-section-title');
        const sqlPreview = data.sql_query || data.sql || 'No SQL generated';
        sqlTitle.innerHTML = `<i class="fas fa-code"></i> SQL: <span class="preview-text">${sqlPreview.length > 50 ? sqlPreview.substring(0, 50) + '...' : sqlPreview}</span>`;
        
        // Set results
        const resultsContent = container.querySelector('.results-content');
        
        // Check for errors first
        if (data.error) {
            const errorDiv = document.createElement('div');
            errorDiv.classList.add('error-message');
            errorDiv.textContent = data.error;
            resultsContent.appendChild(errorDiv);
            
            // Update results header to show error
            const resultsHeader = container.querySelector('[data-section="results"]');
            const resultsTitle = resultsHeader.querySelector('.query-section-title');
            resultsTitle.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Error: <span class="preview-text">${data.error.length > 50 ? data.error.substring(0, 50) + '...' : data.error}</span>`;
            
            // Add error class to container
            container.classList.add('query-error');
        } else if (data.results && data.results.length > 0) {
            const table = document.createElement('table');
            table.classList.add('result-table');
            
            // Create table header
            const thead = document.createElement('thead');
            const headerRow = document.createElement('tr');
            Object.keys(data.results[0]).forEach(column => {
                const th = document.createElement('th');
                th.textContent = column;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);
            
            // Create table body
            const tbody = document.createElement('tbody');
            data.results.forEach(row => {
                const tr = document.createElement('tr');
                Object.values(row).forEach(value => {
                    const td = document.createElement('td');
                    td.textContent = value;
                    tr.appendChild(td);
                });
                tbody.appendChild(tr);
            });
            table.appendChild(tbody);
            
            // Add table to results content
            resultsContent.appendChild(table);
            
            // Create preview for results section
            const resultsHeader = container.querySelector('[data-section="results"]');
            const resultsTitle = resultsHeader.querySelector('.query-section-title');
            resultsTitle.innerHTML = `<i class="fas fa-table"></i> Results: <span class="preview-text">${data.results.length} rows</span>`;
        } else {
            // No results
            const noResults = document.createElement('p');
            noResults.textContent = 'No results returned.';
            resultsContent.appendChild(noResults);
            
            // Update results header
            const resultsHeader = container.querySelector('[data-section="results"]');
            const resultsTitle = resultsHeader.querySelector('.query-section-title');
            resultsTitle.innerHTML = `<i class="fas fa-table"></i> Results: <span class="preview-text">No results</span>`;
        }
        
        // Set confidence score
        container.querySelector('.confidence-score').textContent = `${data.confidence}%`;
        
        // Set interactions
        const interactionList = container.querySelector('.interaction-list');
        data.interaction_logs.forEach(log => {
            const li = document.createElement('li');
            li.textContent = log;
            interactionList.appendChild(li);
        });
        
        // Create preview for confidence section
        const confidenceHeader = container.querySelector('[data-section="confidence"]');
        const confidenceTitle = confidenceHeader.querySelector('.query-section-title');
        confidenceTitle.innerHTML = `<i class="fas fa-brain"></i> Confidence: <span class="preview-text">${data.confidence}%</span>`;
        
        // Set timestamp
        const timestamp = container.querySelector('.query-timestamp');
        const now = new Date();
        timestamp.textContent = `Query executed at ${now.toLocaleTimeString()} on ${now.toLocaleDateString()}`;
        
        // Add event listeners to section headers
        container.querySelectorAll('.query-section-header').forEach(header => {
            header.addEventListener('click', function() {
                this.classList.toggle('active');
                const content = this.nextElementSibling;
                const icon = this.querySelector('i:last-child');
                
                if (this.classList.contains('active')) {
                    content.classList.add('show');
                    icon.className = 'fas fa-chevron-up';
                } else {
                    content.classList.remove('show');
                    icon.className = 'fas fa-chevron-down';
                }
            });
        });
        
        // Setup feedback buttons if query_id is available
        if (data.query_id) {
            const feedbackSection = container.querySelector('.query-feedback');
            const feedbackButtons = feedbackSection.querySelectorAll('.feedback-button');
            const feedbackStatus = feedbackSection.querySelector('.feedback-status');
            
            // Store query ID as a data attribute
            feedbackSection.dataset.queryId = data.query_id;
            
            // Add event listeners to feedback buttons
            feedbackButtons.forEach(button => {
                button.addEventListener('click', function() {
                    // If buttons are disabled, do nothing
                    if (this.classList.contains('disabled')) {
                        return;
                    }
                    
                    const feedback = this.dataset.feedback;
                    const queryId = feedbackSection.dataset.queryId;
                    
                    // Update UI to show selected state
                    feedbackButtons.forEach(btn => {
                        btn.classList.remove('selected');
                    });
                    this.classList.add('selected');
                    
                    // Show loading state
                    feedbackStatus.textContent = 'Submitting feedback...';
                    feedbackStatus.className = 'feedback-status loading';
                    
                    // Submit feedback to server
                    submitFeedback(queryId, feedback, feedbackButtons, feedbackStatus);
                });
            });
        } else {
            // Hide feedback section if no query_id
            const feedbackSection = container.querySelector('.query-feedback');
            feedbackSection.style.display = 'none';
        }
        
        // Apply syntax highlighting
        hljs.highlightElement(sqlContent);
        
        return container;
    }

    // Function to submit feedback
    function submitFeedback(queryId, feedback, buttons, statusElement) {
        // Show loading state
        statusElement.textContent = 'Submitting feedback...';
        statusElement.className = 'feedback-status loading';
        
        fetch('/api/feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query_id: queryId, feedback: feedback })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Show success message
            statusElement.textContent = 'Thank you for your feedback!';
            statusElement.className = 'feedback-status success';
            
            // Disable buttons
            buttons.forEach(button => {
                button.classList.add('disabled');
            });
            
            // Log success
            addLogEntry('Feedback submitted successfully', 'success');
        })
        .catch(error => {
            // Show error message
            statusElement.textContent = 'Error submitting feedback';
            statusElement.className = 'feedback-status error';
            
            // Log error
            addLogEntry(`Error submitting feedback: ${error.message}`, 'error');
        });
    }

    // Function to display results
    function displayResults(data) {
        // Create a new result container
        const resultContainer = createResultContainer(data);
        
        // Add the new result container to the top of the results history
        if (resultsHistory.firstChild) {
            resultsHistory.insertBefore(resultContainer, resultsHistory.firstChild);
        } else {
            resultsHistory.appendChild(resultContainer);
        }
        
        // Scroll to the top to show the new result
        resultsHistory.scrollTop = 0;
    }

    // Function to add log entry
    function addLogEntry(message, type) {
        const logItem = document.createElement('div');
        logItem.classList.add('log-item');
        const timestamp = new Date().toLocaleTimeString();
        logItem.innerHTML = `<strong>[${timestamp}]</strong> ${message}`;
        if (type) logItem.classList.add(`log-${type}`);
        logsContainer.appendChild(logItem);
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }

    // Function to update history
    function updateHistory(history) {
        // Clear history list
        clearContainer(historyList);
        
        // Add new history items
        if (history && history.length > 0) {
            history.forEach(query => {
                const historyItem = document.createElement('div');
                historyItem.classList.add('history-item');
                historyItem.textContent = query;
                historyList.appendChild(historyItem);
            });
        }
    }

    // Initial auto-resize
    if (queryInput) {
        setTimeout(autoResizeInput, 0);
    }
});
