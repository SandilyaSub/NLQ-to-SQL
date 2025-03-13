document.addEventListener('DOMContentLoaded', function() {
    const queryInput = document.getElementById('query-input');
    const submitBtn = document.getElementById('submit-btn');
    const resultsContainer = document.getElementById('results-container');
    const logsContainer = document.getElementById('logs-container');
    const historyList = document.getElementById('history-list');
    
    // Function to auto-resize the input field based on content
    function autoResizeInput() {
        // Reset height to auto to get the correct scrollHeight
        queryInput.style.height = 'auto';
        // Set the height to match the scrollHeight (content height)
        queryInput.style.height = queryInput.scrollHeight + 'px';
    }
    
    // Add event listener for submit button
    submitBtn.addEventListener('click', submitQuery);
    
    // Add event listener for Enter key
    queryInput.addEventListener('keydown', function(event) {
        if (event.key === 'Enter') {
            submitQuery();
        } else {
            // Use setTimeout to let the input value update first
            setTimeout(autoResizeInput, 0);
        }
    });
    
    // Add event listener for input changes to handle paste events
    queryInput.addEventListener('input', autoResizeInput);
    
    // Add event listener for history items
    historyList.addEventListener('click', function(event) {
        if (event.target.classList.contains('history-item')) {
            queryInput.value = event.target.textContent;
            queryInput.focus();
        }
    });
    
    // Function to submit query
    function submitQuery() {
        const question = queryInput.value.trim();
        if (!question) return;
        
        // Clear input
        queryInput.value = '';
        
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
            submitBtn.removeChild(loadingIndicator);
            submitBtn.disabled = false;
            
            // Handle error
            if (data.error) {
                addLogEntry(`Error: ${data.error}`, 'error');
                return;
            }
            
            // Update history
            updateHistory(data.query_history);
            
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
    
    // Function to display results
    function displayResults(data) {
        // Create result item
        const resultItem = document.createElement('div');
        resultItem.classList.add('result-item');
        resultItem.id = 'latest-result';
        
        // Add question
        const questionElement = document.createElement('div');
        questionElement.classList.add('result-question');
        questionElement.textContent = `Q: ${data.question}`;
        resultItem.appendChild(questionElement);
        
        // Add SQL query with confidence score if available
        const sqlElement = document.createElement('div');
        sqlElement.classList.add('result-sql');
        
        // Add confidence score and iterations if available
        if (data.confidence !== undefined) {
            const confidenceSpan = document.createElement('span');
            confidenceSpan.classList.add('confidence-score');
            confidenceSpan.textContent = `Confidence: ${data.confidence}%`;
            confidenceSpan.style.color = data.confidence >= 90 ? 'green' : data.confidence >= 70 ? 'orange' : 'red';
            confidenceSpan.style.fontWeight = 'bold';
            confidenceSpan.style.marginLeft = '10px';
            
            const iterationsSpan = document.createElement('span');
            iterationsSpan.classList.add('iterations-info');
            iterationsSpan.textContent = `Iterations: ${data.iterations || 1}`;
            iterationsSpan.style.marginLeft = '10px';
            iterationsSpan.style.color = '#666';
            
            sqlElement.textContent = data.sql_query + ' ';
            sqlElement.appendChild(confidenceSpan);
            sqlElement.appendChild(iterationsSpan);
        } else {
            sqlElement.textContent = data.sql_query;
        }
        
        resultItem.appendChild(sqlElement);
        
        // Add interaction logs if available
        if (data.interaction_logs && data.interaction_logs.length > 0) {
            const logsElement = document.createElement('div');
            logsElement.classList.add('interaction-logs');
            logsElement.style.marginTop = '10px';
            logsElement.style.fontSize = '0.9em';
            
            const logsToggle = document.createElement('button');
            logsToggle.textContent = 'Show Agent Interaction Logs';
            logsToggle.classList.add('logs-toggle');
            logsToggle.style.marginBottom = '5px';
            logsToggle.style.padding = '2px 5px';
            logsToggle.style.fontSize = '0.8em';
            
            const logsContent = document.createElement('div');
            logsContent.classList.add('logs-content');
            logsContent.style.display = 'none';
            logsContent.style.padding = '10px';
            logsContent.style.backgroundColor = '#f0f8ff'; // Light blue background
            logsContent.style.borderRadius = '5px';
            logsContent.style.border = '1px solid #cce';
            logsContent.style.maxHeight = '300px';
            logsContent.style.overflowY = 'auto';
            
            data.interaction_logs.forEach((log) => {
                const logElement = document.createElement('div');
                logElement.style.marginBottom = '8px';
                logElement.style.borderBottom = '1px dotted #ccc';
                logElement.style.paddingBottom = '5px';
                
                let shouldSetTextContent = true;
                
                // Style based on log content
                if (log.includes('Data Analyst Agent generating')) {
                    logElement.style.color = '#0066cc'; // Blue for Data Analyst Agent
                    logElement.style.fontWeight = 'bold';
                } else if (log.includes('Data Analyst Agent generated SQL')) {
                    logElement.style.color = '#0066cc'; // Blue for Data Analyst Agent
                    // Extract the SQL part
                    const sqlPart = log.substring(log.indexOf(': ') + 2);
                    logElement.innerHTML = log.substring(0, log.indexOf(': ') + 2) + 
                        `<span style="font-family: monospace; background-color: #f5f5f5; padding: 2px 4px; border-radius: 3px;">${sqlPart}</span>`;
                    shouldSetTextContent = false; // Skip the default text setting below
                } else if (log.includes('Validation Agent validating')) {
                    logElement.style.color = '#006600'; // Green for Validation Agent
                    logElement.style.fontWeight = 'bold';
                } else if (log.includes('Validation Agent feedback')) {
                    logElement.style.color = '#006600'; // Green for Validation Agent
                    // Extract confidence score
                    const confidenceMatch = log.match(/confidence: (\d+)%/);
                    if (confidenceMatch) {
                        const confidence = parseInt(confidenceMatch[1]);
                        const confidenceColor = confidence >= 90 ? 'green' : confidence >= 70 ? 'orange' : 'red';
                        logElement.innerHTML = log.replace(
                            /(confidence: \d+%)/,
                            `<span style="color: ${confidenceColor}; font-weight: bold;">$1</span>`
                        );
                        shouldSetTextContent = false; // Skip the default text setting below
                    }
                } else if (log.includes('detailed feedback')) {
                    logElement.style.color = '#990000'; // Dark red for detailed feedback
                } else if (log.includes('Error')) {
                    logElement.style.color = 'red';
                    logElement.style.fontWeight = 'bold';
                } else if (log.includes('Successfully')) {
                    logElement.style.color = 'green';
                    logElement.style.fontWeight = 'bold';
                }
                
                // Only set textContent if we haven't set innerHTML
                if (shouldSetTextContent) {
                    logElement.textContent = log;
                }
                logsContent.appendChild(logElement);
            });
            
            logsToggle.addEventListener('click', function() {
                if (logsContent.style.display === 'none') {
                    logsContent.style.display = 'block';
                    logsToggle.textContent = 'Hide Agent Interaction Logs';
                } else {
                    logsContent.style.display = 'none';
                    logsToggle.textContent = 'Show Agent Interaction Logs';
                }
            });
            
            logsElement.appendChild(logsToggle);
            logsElement.appendChild(logsContent);
            resultItem.appendChild(logsElement);
        }
        
        // Add validation history if available
        if (data.validation_history && data.validation_history.length > 0) {
            const historyElement = document.createElement('div');
            historyElement.classList.add('validation-history');
            historyElement.style.marginTop = '10px';
            historyElement.style.fontSize = '0.9em';
            historyElement.style.color = '#666';
            
            const historyToggle = document.createElement('button');
            historyToggle.textContent = 'Show Validation History';
            historyToggle.classList.add('history-toggle');
            historyToggle.style.marginBottom = '5px';
            historyToggle.style.padding = '2px 5px';
            historyToggle.style.fontSize = '0.8em';
            
            const historyContent = document.createElement('div');
            historyContent.classList.add('history-content');
            historyContent.style.display = 'none';
            historyContent.style.padding = '5px';
            historyContent.style.backgroundColor = '#f5f5f5';
            historyContent.style.borderRadius = '3px';
            
            data.validation_history.forEach((item, index) => {
                const itemElement = document.createElement('div');
                itemElement.style.marginBottom = '5px';
                itemElement.innerHTML = `<strong>Iteration ${index + 1}</strong> (Confidence: ${item.confidence}%)<br/>`;
                itemElement.innerHTML += `<span style="color: #333">SQL: ${item.sql_query}</span><br/>`;
                itemElement.innerHTML += `<span style="color: #666">Feedback: ${item.feedback}</span>`;
                historyContent.appendChild(itemElement);
            });
            
            historyToggle.addEventListener('click', function() {
                if (historyContent.style.display === 'none') {
                    historyContent.style.display = 'block';
                    historyToggle.textContent = 'Hide Validation History';
                } else {
                    historyContent.style.display = 'none';
                    historyToggle.textContent = 'Show Validation History';
                }
            });
            
            historyElement.appendChild(historyToggle);
            historyElement.appendChild(historyContent);
            resultItem.appendChild(historyElement);
        }
        
        // Add results table
        const tableContainer = document.createElement('div');
        tableContainer.classList.add('result-data');
        
        if (data.results && Array.isArray(data.results) && data.results.length > 0) {
            const table = document.createElement('table');
            table.classList.add('result-table');
            
            // Create table header
            const thead = document.createElement('thead');
            const headerRow = document.createElement('tr');
            
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
            
            data.results.forEach(row => {
                const tr = document.createElement('tr');
                
                columns.forEach(column => {
                    const td = document.createElement('td');
                    td.textContent = row[column] !== null ? row[column] : '';
                    tr.appendChild(td);
                });
                
                tbody.appendChild(tr);
            });
            
            table.appendChild(tbody);
            tableContainer.appendChild(table);
        } else if (data.results && data.results.error) {
            // Display error message
            const errorMessage = document.createElement('div');
            errorMessage.classList.add('log-error');
            errorMessage.textContent = data.results.error;
            tableContainer.appendChild(errorMessage);
        } else {
            // Display no results message
            const noResults = document.createElement('div');
            noResults.textContent = 'No results found';
            tableContainer.appendChild(noResults);
        }
        
        resultItem.appendChild(tableContainer);
        
        // Add to results container
        resultsContainer.insertBefore(resultItem, resultsContainer.firstChild);
        
        // Scroll to the latest result
        resultItem.scrollIntoView({ behavior: 'smooth' });
    }
    
    // Function to add log entry
    function addLogEntry(message, type = 'info') {
        const logItem = document.createElement('div');
        logItem.classList.add('log-item', `log-${type}`);
        
        const timestamp = new Date().toLocaleTimeString();
        logItem.textContent = `[${timestamp}] ${message}`;
        
        logsContainer.appendChild(logItem);
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }
    
    // Function to update history
    function updateHistory(history) {
        historyList.innerHTML = '';
        
        history.forEach(query => {
            const historyItem = document.createElement('div');
            historyItem.classList.add('history-item');
            historyItem.textContent = query;
            historyList.appendChild(historyItem);
        });
    }
    
    // Add initial log entry
    addLogEntry('NLQ to SQL Terminal initialized', 'info');
    addLogEntry('Ready to process natural language queries', 'success');
});
