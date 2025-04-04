/**
 * Document Data Extractor
 * Frontend JavaScript for handling document uploads and displaying results
 */

document.addEventListener('DOMContentLoaded', function() {
    // General extraction elements
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('document-file');
    const extractBtn = document.getElementById('extract-btn');
    const loadingSpinner = document.getElementById('loading-spinner');
    const loadingOverlay = document.getElementById('loading-overlay');
    const resultsContainer = document.getElementById('results-container');
    const copyJsonBtn = document.getElementById('copy-json-btn');
    const schemaInput = document.getElementById('extraction-schema');
    
    // Table extraction elements
    const tablesForm = document.getElementById('tables-form');
    const tablesFileInput = document.getElementById('tables-file');
    const extractTablesBtn = document.getElementById('extract-tables-btn');
    const tablesLoadingSpinner = document.getElementById('tables-loading-spinner');
    const tablesResultsContainer = document.getElementById('tables-results-container');
    const copyTablesJsonBtn = document.getElementById('copy-tables-json-btn');
    const tableSelector = document.getElementById('table-selector');
    
    // Store the extracted data for copy functionality
    let extractedData = null;
    
    // Handle form submission
    uploadForm.addEventListener('submit', function(event) {
        event.preventDefault();
        
        // Validate file selection
        if (!fileInput.files || fileInput.files.length === 0) {
            showAlert('danger', 'Please select a document file to upload');
            return;
        }
        
        // Validate schema format if provided
        if (schemaInput.value.trim()) {
            try {
                JSON.parse(schemaInput.value);
            } catch (e) {
                showAlert('danger', 'Invalid JSON schema format: ' + e.message);
                return;
            }
        }
        
        // Start loading state
        startLoading();
        
        // Prepare form data for upload
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        
        if (schemaInput.value.trim()) {
            formData.append('extraction_schema', schemaInput.value);
        }
        
        // Make the API request
        fetch('/api/extract', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            // Store the data for copy functionality
            extractedData = data;
            
            // Display results
            displayResults(data);
            
            // Enable copy button
            copyJsonBtn.disabled = false;
            
            // Show success message
            if (data.success) {
                showAlert('success', 'Document data extracted successfully');
            } else {
                showAlert('warning', 'Extraction completed with errors: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('danger', 'Failed to process document: ' + error.message);
            
            // Reset results area
            resultsContainer.innerHTML = `
                <div class="alert alert-danger">
                    <h4 class="alert-heading">Extraction Failed</h4>
                    <p>${error.message || 'Unknown error occurred during processing'}</p>
                </div>
            `;
        })
        .finally(() => {
            stopLoading();
        });
    });
    
    // Copy JSON button
    copyJsonBtn.addEventListener('click', function() {
        if (!extractedData) return;
        
        const jsonStr = JSON.stringify(extractedData, null, 2);
        navigator.clipboard.writeText(jsonStr).then(
            function() {
                showAlert('info', 'JSON copied to clipboard');
                // Visual feedback
                copyJsonBtn.innerText = 'Copied!';
                setTimeout(() => {
                    copyJsonBtn.innerText = 'Copy JSON';
                }, 2000);
            },
            function() {
                showAlert('danger', 'Failed to copy to clipboard');
            }
        );
    });
    
    /**
     * Display extraction results in the results container
     */
    function displayResults(data) {
        // Clear previous results
        resultsContainer.innerHTML = '';
        
        if (data.success && data.data) {
            // Create results display
            const resultHtml = `
                <div class="results-content">
                    <pre class="json-display">${syntaxHighlight(JSON.stringify(data.data, null, 2))}</pre>
                </div>
            `;
            resultsContainer.innerHTML = resultHtml;
        } else {
            // Show error
            resultsContainer.innerHTML = `
                <div class="alert alert-warning">
                    <h4 class="alert-heading">Extraction Problem</h4>
                    <p>${data.error || 'No data could be extracted from the document'}</p>
                </div>
            `;
        }
    }
    
    /**
     * Reset the results container to its initial state
     */
    function resetResults() {
        resultsContainer.innerHTML = `
            <div class="text-center py-5 text-secondary">
                <i class="fas fa-file-alt fa-3x mb-3"></i>
                <p>Upload a document to see extraction results</p>
            </div>
        `;
        copyJsonBtn.disabled = true;
        extractedData = null;
    }
    
    /**
     * Set UI to loading state
     */
    function startLoading() {
        extractBtn.disabled = true;
        loadingSpinner.classList.remove('d-none');
        loadingOverlay.classList.remove('d-none');
    }
    
    /**
     * Reset UI from loading state
     */
    function stopLoading() {
        extractBtn.disabled = false;
        loadingSpinner.classList.add('d-none');
        loadingOverlay.classList.add('d-none');
    }
    
    /**
     * Show an alert message that fades after a few seconds
     */
    function showAlert(type, message) {
        // Create alert element
        const alertEl = document.createElement('div');
        alertEl.className = `alert alert-${type} alert-dismissible fade show`;
        alertEl.setAttribute('role', 'alert');
        alertEl.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        // Add to the container after the header
        const header = document.querySelector('header');
        header.insertAdjacentElement('afterend', alertEl);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alertEl);
            bsAlert.close();
        }, 5000);
    }
    
    /**
     * Syntax highlight JSON for display
     */
    function syntaxHighlight(json) {
        json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
            let cls = 'json-number';
            if (/^"/.test(match)) {
                if (/:$/.test(match)) {
                    cls = 'json-key';
                } else {
                    cls = 'json-string';
                }
            } else if (/true|false/.test(match)) {
                cls = 'json-boolean';
            } else if (/null/.test(match)) {
                cls = 'json-null';
            }
            return '<span class="' + cls + '">' + match + '</span>';
        });
    }
    
    // Reset file input when modal is closed
    fileInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            // Show file name
            const fileName = this.files[0].name;
            this.nextElementSibling = fileName;
        }
    });
    
    // Add example schema button
    const exampleBtn = document.createElement('button');
    exampleBtn.type = 'button';
    exampleBtn.className = 'btn btn-sm btn-link mt-1';
    exampleBtn.textContent = 'Load Example Schema';
    exampleBtn.addEventListener('click', function() {
        const exampleSchema = {
            "fields": [
                {"name": "invoice_number", "description": "The invoice identification number"},
                {"name": "date", "description": "The invoice date"},
                {"name": "total_amount", "description": "The total amount due"},
                {"name": "customer", "description": "Customer name and details"},
                {"name": "items", "description": "List of items, quantities and prices"}
            ]
        };
        schemaInput.value = JSON.stringify(exampleSchema, null, 2);
    });
    
    // Insert the button after the schema input
    schemaInput.parentElement.appendChild(exampleBtn);

    // Variable to store extracted tables data
    let extractedTablesData = null;

    // Handle table extraction form submission
    tablesForm.addEventListener('submit', function(event) {
        event.preventDefault();
        
        // Validate file selection
        if (!tablesFileInput.files || tablesFileInput.files.length === 0) {
            showAlert('danger', 'Please select a PDF file to upload');
            return;
        }
        
        // Validate file type
        const fileName = tablesFileInput.files[0].name;
        if (!fileName.toLowerCase().endsWith('.pdf')) {
            showAlert('danger', 'Only PDF files are supported for table extraction');
            return;
        }
        
        // Start loading state for tables
        startTablesLoading();
        
        // Prepare form data for upload
        const formData = new FormData();
        formData.append('file', tablesFileInput.files[0]);
        
        // Make the API request to extract tables
        fetch('/api/extract-tables', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            // Check if response is OK
            if (!response.ok) {
                throw new Error(`Server responded with status ${response.status}`);
            }
            
            // Check for timeout or other errors
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                throw new Error('Server response was not in JSON format. The operation might have timed out or encountered an error.');
            }
            
            return response.json();
        })
        .then(data => {
            // Store the data for copy functionality
            extractedTablesData = data;
            
            // Display table results
            displayTablesResults(data);
            
            // Enable copy button
            copyTablesJsonBtn.disabled = false;
            
            // Show success message
            if (data.success && data.tables && data.tables.length > 0) {
                showAlert('success', `Successfully extracted ${data.total_tables} tables from ${data.pages_processed} pages`);
            } else if (data.success && (!data.tables || data.tables.length === 0)) {
                showAlert('warning', 'No tables found in the document');
            } else {
                showAlert('warning', 'Table extraction completed with errors: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            
            // Show more user-friendly error message for timeout
            if (error.message.includes('timed out') || error.message.includes('not in JSON format')) {
                showAlert('danger', 'The table extraction process timed out. Please try with a smaller PDF document or fewer pages.');
            } else {
                showAlert('danger', 'Failed to process document: ' + error.message);
            }
            
            // Reset table results area
            tablesResultsContainer.innerHTML = `
                <div class="alert alert-danger">
                    <h4 class="alert-heading">Table Extraction Failed</h4>
                    <p class="mb-0">The document processing may have timed out because:</p>
                    <ul>
                        <li>The PDF has too many pages</li>
                        <li>The tables are too complex</li>
                        <li>The server is currently busy</li>
                    </ul>
                    <p>Please try with a smaller PDF document (5 pages or fewer) for best results.</p>
                </div>
            `;
        })
        .finally(() => {
            stopTablesLoading();
        });
    });

    // Copy Tables JSON button
    copyTablesJsonBtn.addEventListener('click', function() {
        if (!extractedTablesData) return;
        
        const jsonStr = JSON.stringify(extractedTablesData, null, 2);
        navigator.clipboard.writeText(jsonStr).then(
            function() {
                showAlert('info', 'Tables JSON copied to clipboard');
                // Visual feedback
                copyTablesJsonBtn.innerText = 'Copied!';
                setTimeout(() => {
                    copyTablesJsonBtn.innerText = 'Copy JSON';
                }, 2000);
            },
            function() {
                showAlert('danger', 'Failed to copy to clipboard');
            }
        );
    });

    // Table selector change event
    tableSelector.addEventListener('change', function() {
        const selectedIndex = this.value;
        
        if (!selectedIndex || !extractedTablesData || !extractedTablesData.tables) {
            return;
        }
        
        // Show the selected table
        displayTableDetails(extractedTablesData.tables[selectedIndex]);
    });

    /**
     * Display table extraction results
     */
    function displayTablesResults(data) {
        // Clear previous results
        tablesResultsContainer.innerHTML = '';
        
        // Reset table selector
        tableSelector.innerHTML = '<option value="">Select a table...</option>';
        tableSelector.classList.add('d-none');
        
        if (data.success && data.tables && data.tables.length > 0) {
            // Create summary of tables
            const summaryHtml = `
                <div class="mb-4">
                    <h4>Tables Found: ${data.total_tables}</h4>
                    <p>Processed ${data.pages_processed} out of ${data.total_pages} pages</p>
                </div>
            `;
            
            // Add tables to selector
            data.tables.forEach((table, index) => {
                const tableTitle = table.table_title || `Table ${index + 1} (Page ${table.page_number})`;
                const option = document.createElement('option');
                option.value = index;
                option.textContent = tableTitle;
                tableSelector.appendChild(option);
            });
            
            // Show the selector
            tableSelector.classList.remove('d-none');
            
            // Display the first table by default
            const firstTableHtml = renderTableHtml(data.tables[0]);
            
            tablesResultsContainer.innerHTML = summaryHtml + firstTableHtml;
        } else if (data.success && (!data.tables || data.tables.length === 0)) {
            // No tables found
            tablesResultsContainer.innerHTML = `
                <div class="alert alert-warning">
                    <h4 class="alert-heading">No Tables Found</h4>
                    <p>The document was processed successfully, but no tables were detected.</p>
                    <p class="mb-0">Try a different document or ensure that tables in the document have clear boundaries.</p>
                </div>
            `;
        } else {
            // Show error
            tablesResultsContainer.innerHTML = `
                <div class="alert alert-warning">
                    <h4 class="alert-heading">Table Extraction Problem</h4>
                    <p>${data.error || 'No tables could be extracted from the document'}</p>
                </div>
            `;
        }
    }

    /**
     * Display details of a specific table
     */
    function displayTableDetails(tableData) {
        // Get the table container
        const tableContainer = document.createElement('div');
        tableContainer.innerHTML = renderTableHtml(tableData);
        
        // Find existing summary section
        const summarySection = tablesResultsContainer.querySelector('div:first-child');
        
        // Replace everything but the summary with the new table
        tablesResultsContainer.innerHTML = '';
        if (summarySection) {
            tablesResultsContainer.appendChild(summarySection);
        }
        tablesResultsContainer.appendChild(tableContainer);
    }

    /**
     * Render HTML for a table
     */
    function renderTableHtml(tableData) {
        if (!tableData || !tableData.headers || !tableData.data) {
            return '<div class="alert alert-warning">Invalid table data</div>';
        }
        
        // Create table title
        const titleHtml = tableData.table_title ? 
            `<h4 class="mb-3">${tableData.table_title}</h4>` : 
            '';
        
        // Create page info
        const pageInfo = tableData.page_number ? 
            `<div class="text-muted mb-3">Found on page ${tableData.page_number}</div>` : 
            '';
        
        // Create table headers
        const headersHtml = tableData.headers.map(header => 
            `<th scope="col">${header}</th>`
        ).join('');
        
        // Create table rows
        const rowsHtml = tableData.data.map(row => 
            `<tr>${row.map(cell => `<td>${cell}</td>`).join('')}</tr>`
        ).join('');
        
        // Create complete table HTML
        return `
            <div class="table-container">
                ${titleHtml}
                ${pageInfo}
                <div class="table-responsive">
                    <table class="table table-striped table-bordered">
                        <thead class="thead-dark">
                            <tr>${headersHtml}</tr>
                        </thead>
                        <tbody>
                            ${rowsHtml}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }

    /**
     * Start loading state for table extraction
     */
    function startTablesLoading() {
        extractTablesBtn.disabled = true;
        tablesLoadingSpinner.classList.remove('d-none');
        loadingOverlay.classList.remove('d-none');
    }
    
    /**
     * Stop loading state for table extraction
     */
    function stopTablesLoading() {
        extractTablesBtn.disabled = false;
        tablesLoadingSpinner.classList.add('d-none');
        loadingOverlay.classList.add('d-none');
    }
});