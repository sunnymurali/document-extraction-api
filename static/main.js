/**
 * Document Data Extractor
 * Frontend JavaScript for handling document uploads and displaying results
 * Enhanced with asynchronous processing to handle large documents without blocking
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log("Document Data Extractor loaded");
    
    // General extraction elements
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('document-file');
    const useChunkingCheckbox = document.getElementById('use-chunking');
    const extractBtn = document.getElementById('extract-btn');
    const loadingSpinner = document.getElementById('loading-spinner');
    const loadingOverlay = document.getElementById('loading-overlay');
    const resultsContainer = document.getElementById('results-container');
    const copyJsonBtn = document.getElementById('copy-json-btn');
    const schemaInput = document.getElementById('extraction-schema');
    
    // Progress tracking elements
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('extraction-progress');
    const progressText = document.getElementById('progress-text');
    
    // Field builder elements
    const fieldsContainer = document.getElementById('fields-container');
    const addFieldBtn = document.getElementById('add-field-btn');
    const toggleJsonViewBtn = document.getElementById('toggle-json-view');
    const jsonSchemaContainer = document.getElementById('json-schema-container');
    const fieldsBuilder = document.getElementById('fields-builder');
    const noFieldsMessage = document.getElementById('no-fields-message');
    
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
    let fieldCount = 0;
    
    // Store active document status polling
    let statusPollingInterval = null;
    let activeDocumentId = null;
    
    // Handle form submission - now a two-step process (upload then extract)
    uploadForm.addEventListener('submit', function(event) {
        event.preventDefault();
        console.log("Form submitted");
        
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
        
        // Reset progress display
        resetProgress();
        showProgress();
        
        // STEP 1: Upload the document
        uploadDocument()
            .then(uploadResult => {
                if (!uploadResult.success) {
                    throw new Error(uploadResult.error || 'Document upload failed');
                }
                
                console.log("Document uploaded successfully", uploadResult);
                showAlert('success', 'Document uploaded successfully');
                updateProgress('Uploaded document', 20);
                
                // Store the document ID for future reference
                activeDocumentId = uploadResult.document_id;
                
                // STEP 2: Start the extraction process
                return startExtraction(uploadResult.document_id);
            })
            .then(extractionResult => {
                if (!extractionResult.success) {
                    throw new Error(extractionResult.error || 'Failed to start extraction');
                }
                
                console.log("Extraction started", extractionResult);
                showAlert('info', 'Extraction started. Processing document...');
                updateProgress('Processing document', 30);
                
                // STEP 3: Begin polling for status
                startStatusPolling(activeDocumentId);
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('danger', 'Error: ' + error.message);
                stopLoading();
                hideProgress();
            });
    });
    
    // Upload the document to the server
    function uploadDocument() {
        console.log("Uploading document...");
        // Prepare form data for upload
        const formData = new FormData();
        const fileToUpload = fileInput.files[0];
        formData.append('file', fileToUpload);
        
        // Update progress with file information
        const fileSizeMB = (fileToUpload.size / (1024 * 1024)).toFixed(2);
        updateProgress(`Uploading ${fileToUpload.name} (${fileSizeMB} MB)`, 10);
        
        return fetch('/api/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            // Special handling for upload errors
            if (!response.ok) {
                if (response.status === 400) {
                    // For 400 errors, we want to show the specific error message
                    return response.json().then(errorData => {
                        const errorMessage = errorData.error || 'Invalid file format or content';
                        showAlert('danger', `Upload failed: ${errorMessage}`);
                        throw new Error(errorMessage);
                    });
                }
                // For other errors, use default handling
                return handleResponse(response);
            }
            return response.json();
        });
    }
    
    // Start the extraction process
    function startExtraction(documentId) {
        console.log("Starting extraction for document:", documentId);
        // Prepare the extraction request
        const extractionRequest = {
            document_id: documentId,
            use_chunking: useChunkingCheckbox.checked,
        };
        
        // Add schema if provided
        if (schemaInput.value.trim()) {
            extractionRequest.extraction_schema = JSON.parse(schemaInput.value);
        }
        
        return fetch('/api/extract', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(extractionRequest)
        })
        .then(handleResponse);
    }
    
    // Start polling for document status
    function startStatusPolling(documentId) {
        console.log("Starting status polling for document:", documentId);
        // Clear any existing polling
        stopStatusPolling();
        
        // Set up polling interval (check every 2 seconds)
        statusPollingInterval = setInterval(() => {
            checkDocumentStatus(documentId)
                .then(statusResult => {
                    if (!statusResult.success) {
                        throw new Error(statusResult.error || 'Failed to get document status');
                    }
                    
                    console.log("Document status:", statusResult);
                    
                    // Update progress based on status
                    const status = statusResult.status;
                    updateProgressFromStatus(status, statusResult);
                    
                    // If completed or failed, stop polling and fetch results
                    if (status === 'completed') {
                        stopStatusPolling();
                        
                        // Fetch the extraction results
                        fetchExtractionResults(documentId)
                            .then(resultData => {
                                if (!resultData.success) {
                                    throw new Error(resultData.error || 'Failed to get extraction results');
                                }
                                
                                // Display the results
                                displayResults(resultData.data);
                                
                                // Store the data for copy functionality
                                extractedData = resultData.data;
                                
                                // Update progress and stop loading
                                updateProgress('Extraction completed', 100, 'success');
                                stopLoading();
                                showAlert('success', 'Extraction completed successfully');
                            })
                            .catch(error => {
                                console.error('Error fetching results:', error);
                                updateProgress('Failed to get results: ' + error.message, 0, 'danger');
                                stopLoading();
                                showAlert('danger', 'Error fetching results: ' + error.message);
                            });
                    } else if (status === 'failed') {
                        stopStatusPolling();
                        updateProgress('Extraction failed: ' + (statusResult.error || 'Unknown error'), 0, 'danger');
                        stopLoading();
                        showAlert('danger', 'Extraction failed: ' + (statusResult.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    console.error('Error polling status:', error);
                    updateProgress('Error checking status: ' + error.message, 0, 'warning');
                    // Don't stop polling on transient errors
                });
        }, 2000);
    }
    
    // Stop status polling
    function stopStatusPolling() {
        if (statusPollingInterval) {
            clearInterval(statusPollingInterval);
            statusPollingInterval = null;
        }
    }
    
    // Check the status of a document
    function checkDocumentStatus(documentId) {
        console.log("Checking status for document:", documentId);
        return fetch(`/api/status/${documentId}`)
            .then(handleResponse);
    }
    
    // Fetch extraction results
    function fetchExtractionResults(documentId) {
        console.log("Fetching results for document:", documentId);
        return fetch(`/api/result/${documentId}`)
            .then(handleResponse);
    }
    
    // Standard response handler
    function handleResponse(response) {
        // First check if the response is ok
        if (!response.ok) {
            console.error("Response not OK:", response.status, response.statusText);
            // Check if response is HTML
            if (response.headers.get('content-type')?.includes('text/html')) {
                return response.text().then(html => {
                    throw new Error('Server returned HTML instead of JSON. This typically indicates a server error or authorization problem.');
                });
            }
            throw new Error(`Server responded with status: ${response.status}`);
        }
        return response.json();
    }
    
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
    
    // Tables Copy JSON button
    copyTablesJsonBtn.addEventListener('click', function() {
        const tableResults = document.getElementById('tables-json-output');
        if (!tableResults || !tableResults.textContent) return;
        
        navigator.clipboard.writeText(tableResults.textContent).then(
            function() {
                showAlert('info', 'Tables JSON copied to clipboard');
                // Visual feedback
                copyTablesJsonBtn.innerText = 'Copied!';
                setTimeout(() => {
                    copyTablesJsonBtn.innerText = 'Copy Tables JSON';
                }, 2000);
            },
            function() {
                showAlert('danger', 'Failed to copy to clipboard');
            }
        );
    });
    
    // Handle table form submission
    tablesForm.addEventListener('submit', function(event) {
        event.preventDefault();
        
        // Validate file selection
        if (!tablesFileInput.files || tablesFileInput.files.length === 0) {
            showAlert('danger', 'Please select a PDF file to extract tables from');
            return;
        }
        
        // Check file type
        const file = tablesFileInput.files[0];
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            showAlert('danger', 'Table extraction only supports PDF files');
            return;
        }
        
        // Reset previous results
        tablesResultsContainer.innerHTML = '';
        tablesResultsContainer.style.display = 'none';
        
        // Start loading state
        startTablesLoading();
        
        // Prepare form data for upload
        const formData = new FormData();
        formData.append('file', file);
        
        // Upload and extract tables
        fetch('/api/extract-tables', {
            method: 'POST',
            body: formData
        })
        .then(handleResponse)
        .then(result => {
            stopTablesLoading();
            
            if (!result.success) {
                showAlert('danger', 'Table extraction failed: ' + (result.error || 'Unknown error'));
                return;
            }
            
            // Display the table extraction results
            displayTablesResults(result);
        })
        .catch(error => {
            console.error('Error extracting tables:', error);
            stopTablesLoading();
            showAlert('danger', 'Error: ' + error.message);
        });
    });
    
    // Toggle JSON view button for schema input
    toggleJsonViewBtn.addEventListener('click', function() {
        // Update schema input if we're in fields mode
        if (jsonSchemaContainer.style.display === 'none') {
            updateSchemaFromFields();
        }
        
        // Toggle display
        const isJsonVisible = jsonSchemaContainer.style.display !== 'none';
        jsonSchemaContainer.style.display = isJsonVisible ? 'none' : 'block';
        fieldsBuilder.style.display = isJsonVisible ? 'block' : 'none';
        
        // Update button text
        toggleJsonViewBtn.textContent = isJsonVisible ? 'Edit JSON' : 'Edit Fields';
        
        // If switching back to fields, update them from the schema
        if (isJsonVisible) {
            updateFieldsFromSchema();
        }
    });
    
    // Add Field button
    addFieldBtn.addEventListener('click', function() {
        addField();
        updateFieldDisplay();
    });
    
    /**
     * Display extraction results in the results container
     */
    function displayResults(data) {
        // Clear previous results
        resetResults();
        
        // Show the container
        resultsContainer.style.display = 'block';
        
        // Get pre element for results
        const preElement = document.getElementById('json-output');
        
        // Format the data
        const formattedJson = syntaxHighlight(JSON.stringify(data, null, 2));
        
        // Add formatted JSON to the results
        preElement.innerHTML = formattedJson;
    }
    
    /**
     * Reset the results container to its initial state
     */
    function resetResults() {
        // Reset extracted data
        extractedData = null;
        
        // Reset the results container
        resultsContainer.style.display = 'none';
        
        // Clear any previous results
        const preElement = document.getElementById('json-output');
        if (preElement) {
            preElement.innerHTML = '';
        }
    }
    
    /**
     * Set UI to loading state
     */
    function startLoading() {
        loadingSpinner.style.display = 'block';
        loadingOverlay.style.display = 'flex';
        extractBtn.disabled = true;
    }
    
    /**
     * Reset UI from loading state
     */
    function stopLoading() {
        loadingSpinner.style.display = 'none';
        loadingOverlay.style.display = 'none';
        extractBtn.disabled = false;
    }
    
    /**
     * Show progress container
     */
    function showProgress() {
        progressContainer.style.display = 'block';
    }
    
    /**
     * Hide progress container
     */
    function hideProgress() {
        progressContainer.style.display = 'none';
    }
    
    /**
     * Reset progress display
     */
    function resetProgress() {
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
        progressBar.className = 'progress-bar';
        progressText.textContent = 'Initializing...';
    }
    
    /**
     * Update progress display
     */
    function updateProgress(message, percentage, className = null) {
        progressBar.style.width = `${percentage}%`;
        progressBar.textContent = `${percentage}%`;
        progressText.textContent = message;
        
        if (className) {
            progressBar.className = `progress-bar bg-${className}`;
        } else {
            progressBar.className = 'progress-bar';
        }
    }
    
    /**
     * Update progress based on document status
     */
    function updateProgressFromStatus(status, statusData) {
        let progressPercent = 30; // Default starting progress
        
        if (status === 'pending') {
            updateProgress('Document pending extraction...', 30);
        } else if (status === 'processing') {
            // Calculate progress based on extraction status if available
            if (statusData.extraction_status) {
                const totalFields = Object.keys(statusData.extraction_status).length || 1;
                let completedFields = 0;
                
                // Count completed fields
                for (const field in statusData.extraction_status) {
                    if (statusData.extraction_status[field] === 'completed') {
                        completedFields++;
                    }
                }
                
                // Calculate progress percentage
                const fieldProgress = totalFields > 0 ? (completedFields / totalFields) : 0;
                progressPercent = 30 + Math.round(fieldProgress * 50); // Scale between 30-80%
            } else {
                progressPercent = 40; // Generic progress if no field status
            }
            
            updateProgress(`Processing document... (${progressPercent}%)`, progressPercent);
        } else if (status === 'completed') {
            updateProgress('Fetching results...', 90);
        } else if (status === 'failed') {
            updateProgress(`Extraction failed: ${statusData.error || 'Unknown error'}`, 0, 'danger');
        }
    }
    
    /**
     * Show an alert message that fades after a few seconds
     */
    function showAlert(type, message) {
        const alertsContainer = document.getElementById('alerts-container');
        
        // Create alert element
        const alertElement = document.createElement('div');
        alertElement.className = `alert alert-${type} alert-dismissible fade show`;
        alertElement.role = 'alert';
        alertElement.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        // Add the alert to the container
        alertsContainer.appendChild(alertElement);
        
        // Initialize the alert with bootstrap
        const bsAlert = new bootstrap.Alert(alertElement);
        
        // Set timeout to auto-dismiss after 5 seconds
        setTimeout(() => {
            try {
                bsAlert.close();
            } catch (e) {
                alertElement.remove();
            }
        }, 5000);
    }
    
    /**
     * Syntax highlight JSON for display
     */
    function syntaxHighlight(json) {
        json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function(match) {
            let cls = 'number';
            if (/^"/.test(match)) {
                if (/:$/.test(match)) {
                    cls = 'key';
                } else {
                    cls = 'string';
                }
            } else if (/true|false/.test(match)) {
                cls = 'boolean';
            } else if (/null/.test(match)) {
                cls = 'null';
            }
            return '<span class="' + cls + '">' + match + '</span>';
        });
    }
    
    // Field builder functionality
    function addField(name = '', description = '') {
        fieldCount++;
        
        const fieldId = `field-${fieldCount}`;
        const fieldRow = document.createElement('div');
        fieldRow.className = 'field-row mb-3';
        fieldRow.dataset.fieldId = fieldId;
        
        fieldRow.innerHTML = `
            <div class="row">
                <div class="col-md-5">
                    <input type="text" class="form-control field-name" placeholder="Field name" value="${name}">
                </div>
                <div class="col-md-6">
                    <input type="text" class="form-control field-description" placeholder="Description (optional)" value="${description}">
                </div>
                <div class="col-md-1">
                    <button type="button" class="btn btn-danger btn-sm delete-field" aria-label="Delete field">×</button>
                </div>
            </div>
        `;
        
        // Add delete button functionality
        const deleteBtn = fieldRow.querySelector('.delete-field');
        deleteBtn.addEventListener('click', function() {
            fieldRow.remove();
            updateFieldDisplay();
            updateSchemaFromFields();
        });
        
        // Add input change listeners
        const nameInput = fieldRow.querySelector('.field-name');
        const descInput = fieldRow.querySelector('.field-description');
        
        nameInput.addEventListener('input', updateSchemaFromFields);
        descInput.addEventListener('input', updateSchemaFromFields);
        
        // Add to container
        fieldsContainer.appendChild(fieldRow);
    }
    
    function updateFieldDisplay() {
        const fields = fieldsContainer.querySelectorAll('.field-row');
        if (fields.length === 0) {
            noFieldsMessage.style.display = 'block';
        } else {
            noFieldsMessage.style.display = 'none';
        }
    }
    
    function updateSchemaFromFields() {
        const fields = fieldsContainer.querySelectorAll('.field-row');
        const schema = {
            fields: []
        };
        
        fields.forEach(field => {
            const nameInput = field.querySelector('.field-name');
            const descInput = field.querySelector('.field-description');
            
            if (nameInput.value.trim()) {
                schema.fields.push({
                    name: nameInput.value.trim(),
                    description: descInput.value.trim()
                });
            }
        });
        
        schemaInput.value = JSON.stringify(schema, null, 2);
    }
    
    function updateFieldsFromSchema() {
        // Clear existing fields
        fieldsContainer.innerHTML = '';
        fieldCount = 0;
        
        // Try to parse the schema
        try {
            if (schemaInput.value.trim()) {
                const schema = JSON.parse(schemaInput.value);
                
                if (schema && schema.fields && Array.isArray(schema.fields)) {
                    schema.fields.forEach(field => {
                        if (field.name) {
                            addField(field.name, field.description || '');
                        }
                    });
                }
            }
        } catch (e) {
            console.error('Error parsing schema:', e);
            showAlert('danger', 'Invalid schema format: ' + e.message);
        }
        
        // Update the field display
        updateFieldDisplay();
    }
    
    /**
     * Display table extraction results
     */
    function displayTablesResults(data) {
        // Clear previous results
        tablesResultsContainer.innerHTML = '';
        
        // Format JSON output
        const jsonOutput = document.createElement('pre');
        jsonOutput.id = 'tables-json-output';
        jsonOutput.className = 'json-output mt-3';
        jsonOutput.textContent = JSON.stringify(data, null, 2);
        
        // Create table selector if multiple tables were found
        const tables = data.tables || [];
        const tableCount = tables.length;
        const tableInfo = document.createElement('div');
        tableInfo.className = 'alert alert-info';
        
        if (tableCount > 0) {
            tableInfo.textContent = `Found ${tableCount} tables in the document`;
            
            // Create table selector
            const selectorContainer = document.createElement('div');
            selectorContainer.className = 'form-group mb-3';
            
            const label = document.createElement('label');
            label.htmlFor = 'table-select';
            label.className = 'form-label';
            label.textContent = 'Select a table to view:';
            
            const select = document.createElement('select');
            select.id = 'table-select';
            select.className = 'form-select';
            
            tables.forEach((table, index) => {
                const option = document.createElement('option');
                option.value = index;
                option.textContent = table.table_title || `Table ${index + 1}`;
                select.appendChild(option);
            });
            
            selectorContainer.appendChild(label);
            selectorContainer.appendChild(select);
            
            // Create table display area
            const tableDisplay = document.createElement('div');
            tableDisplay.id = 'table-display';
            tableDisplay.className = 'table-responsive';
            
            // Add event listener to selector
            select.addEventListener('change', function() {
                const selectedTable = tables[this.value];
                displayTableDetails(selectedTable);
            });
            
            // Display the first table initially
            if (tables.length > 0) {
                displayTableDetails(tables[0]);
            }
            
            // Add elements to the page
            tablesResultsContainer.appendChild(tableInfo);
            tablesResultsContainer.appendChild(selectorContainer);
            tablesResultsContainer.appendChild(tableDisplay);
            tablesResultsContainer.appendChild(jsonOutput);
        } else {
            tableInfo.textContent = 'No tables found in the document';
            tableInfo.className = 'alert alert-warning';
            
            tablesResultsContainer.appendChild(tableInfo);
            tablesResultsContainer.appendChild(jsonOutput);
        }
        
        // Show the container
        tablesResultsContainer.style.display = 'block';
    }
    
    /**
     * Display details of a specific table
     */
    function displayTableDetails(tableData) {
        const tableDisplay = document.getElementById('table-display');
        if (!tableDisplay) return;
        
        // Clear previous table display
        tableDisplay.innerHTML = '';
        
        // Add table title
        const titleElement = document.createElement('h4');
        titleElement.textContent = tableData.table_title || 'Table';
        titleElement.className = 'mt-3 mb-2';
        
        // Render the table as HTML
        const tableHtml = renderTableHtml(tableData);
        
        // Add to display
        tableDisplay.appendChild(titleElement);
        tableDisplay.appendChild(tableHtml);
    }
    
    /**
     * Render HTML for a table
     */
    function renderTableHtml(tableData) {
        // Create table element
        const table = document.createElement('table');
        table.className = 'table table-striped table-bordered';
        
        // Create table header
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        
        // Add headers
        const headers = tableData.headers || [];
        headers.forEach(header => {
            const th = document.createElement('th');
            th.textContent = header;
            headerRow.appendChild(th);
        });
        
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        // Create table body
        const tbody = document.createElement('tbody');
        
        // Add rows
        const rows = tableData.data || [];
        rows.forEach(row => {
            const tr = document.createElement('tr');
            
            // Add cells
            row.forEach(cell => {
                const td = document.createElement('td');
                td.textContent = cell;
                tr.appendChild(td);
            });
            
            tbody.appendChild(tr);
        });
        
        table.appendChild(tbody);
        
        return table;
    }
    
    /**
     * Start loading state for table extraction
     */
    function startTablesLoading() {
        tablesLoadingSpinner.style.display = 'block';
        extractTablesBtn.disabled = true;
    }
    
    /**
     * Stop loading state for table extraction
     */
    function stopTablesLoading() {
        tablesLoadingSpinner.style.display = 'none';
        extractTablesBtn.disabled = false;
    }
    
    // Add event listeners to field name inputs to update schema in real-time
    document.addEventListener('input', function(event) {
        if (event.target.classList.contains('field-name') || 
            event.target.classList.contains('field-description')) {
            updateSchemaFromFields();
        }
    });
    
    // Initialize field builder display
    updateFieldDisplay();
    
    // Set JSON container to initially hidden
    jsonSchemaContainer.style.display = 'none';
});
