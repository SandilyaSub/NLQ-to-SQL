document.addEventListener('DOMContentLoaded', function() {

    const queryInput = document.getElementById('query-input');
    const submitBtn = document.getElementById('submit-btn');
    const resultsContainer = document.getElementById('results-container');
    const logsContainer = document.getElementById('logs-container');
    const historyList = document.getElementById('history-list');

    // Section Elements to display
    const queryDetailsContainer = document.querySelector('.query-details-container');
    const interactionsContainer = document.querySelector('.interactions-container');
    const resultsTableContainer = document.querySelector('.results-table-container');

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
        // Helper Variables
        const queryTextSpan = queryDetailsContainer.querySelector('.query-text');
        const sqlCodeElement = queryDetailsContainer.querySelector('.sql-code');
        const confidenceScoreSpan = interactionsContainer.querySelector('.confidence-score');
        const interactionList = interactionsContainer.querySelector('.interaction-list');

        // Set the basic Values correctly
        queryTextSpan.textContent = data.question;
        // Truncate query
        const sqlQuery = data.sql_query;
        const firstLine = sqlQuery.split('\n')[0]; // Get the first line
        sqlCodeElement.textContent = firstLine; // Assign first line to preview area
        sqlCodeElement.title = sqlQuery; // Assign the whole sql code to view on hover of the sql preview section.
        confidenceScoreSpan.textContent = `${data.confidence}%`;

        // Set the SQL highlighting
        hljs.highlightElement(sqlCodeElement);

        // Update the Interactions List
        clearContainer(interactionList); // Clear existing interactions
        data.interaction_logs.forEach(log => {
            const li = document.createElement('li');
            li.textContent = log;
            interactionList.appendChild(li);
        });

        // Now the more complex table rendering
        clearContainer(resultsTableContainer);
        if (data.results && data.results.length > 0) {
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
                const tableRow = document.createElement('tr');
                Object.values(row).forEach(value => {
                    const td = document.createElement('td');
                    td.textContent = value;
                    tableRow.appendChild(td);
                });
                tbody.appendChild(tableRow);
            });
            table.appendChild(tbody);
            resultsTableContainer.appendChild(table);
        } else {
            resultsTableContainer.textContent = 'No results found.';
        }

        // Now we populate all values , for the display

        /* Old Code was replaced with logic shown above
        // Clear previous results
        resultsContainer.innerHTML = '';

        // User Question
        const userQuestionDiv = document.createElement('div');
        userQuestionDiv.classList.add('user-question');
        userQuestionDiv.textContent = data.question;
        resultsContainer.appendChild(userQuestionDiv);

        // Model Response Container
        const modelResponseDiv = document.createElement('div');
        modelResponseDiv.classList.add('model-response');

        // SQL Code
        const sqlCode = document.createElement('pre');
        sqlCode.innerHTML = `<code class="language-sql">${data.sql_query}</code>`;
        hljs.highlightElement(sqlCode);
        modelResponseDiv.appendChild(sqlCode);

        // Results Table
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
                const tableRow = document.createElement('tr');
                columns.forEach(column => {
                    const td = document.createElement('td');
                    td.textContent = row[column];
                    tableRow.appendChild(tableRow);
                });
                tbody.appendChild(tableRow);
            });
            table.appendChild(tbody);
            modelResponseDiv.appendChild(table);
        } else {
            modelResponseDiv.textContent = "No results found.";
        }

        resultsContainer.appendChild(modelResponseDiv);
        */
    }

    // Function to add log entry
    function addLogEntry(message, type) {
        const logItem = document.createElement('div');
        logItem.classList.add('log-item');
        logItem.innerHTML = `<strong>[${new Date().toLocaleTimeString()}]</strong> ${message}`;
        logsContainer.appendChild(logItem);
        logsContainer.scrollTop = logsContainer.scrollHeight;  // Scroll to bottom
    }

    // Function to update history
    function updateHistory(history) {
        historyList.innerHTML = ''; // Clear previous history
        history.forEach(item => {
            const historyItem = document.createElement('div');
            historyItem.classList.add('history-item');
            historyItem.textContent = item;
            historyList.appendChild(historyItem);
        });
    }

   // Collapsible functionality

    const coll = document.getElementsByClassName("collapsible");

    for (let i = 0; i < coll.length; i++) {

        coll[i].addEventListener("click", function() {

            this.classList.toggle("active");

            var content = this.nextElementSibling;

            if (content.style.maxHeight){

                content.style.maxHeight = null;

            } else {

                content.style.maxHeight = content.scrollHeight + "px";

            }

        });

    }

    // Initial auto-resize

    autoResizeInput();

});
