/**
 * Document Data Extractor
 * Frontend JavaScript for handling document uploads and displaying results
 * Enhanced with asynchronous processing to handle large documents without blocking
 */
document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements - General Extraction
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('document-file');
    const schemaInput = document.getElementById('extraction-schema');
    const jsonSchemaContainer = document.getElementById('json-schema-container');
    const fieldsBuilder = document.getElementById('fields-builder');
    const fieldsContainer = document.getElementById('fields-container');
    const noFieldsMessage = document.getElementById('no-fields-message');
    const addFieldBtn = document.getElementById('add-field-btn');
    const toggleJsonViewBtn = document.getElementById('toggle-json-view');
    const useChunkingCheckbox = document.getElementById('use-chunking');
    const extractBtn = document.getElementById('extract-btn');
    const loadingSpinner = document.getElementById('loading-spinner');
    const loadingOverlay = document.getElementById('loading-overlay');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('extraction-progress');
    const progressText = document.getElementById('progress-text');
    const resultsContainer = document.getElementById('results-container');
    const copyJsonBtn = document.getElementById('copy-json-btn');
    
    // DOM Elements - Table Extraction
    const tablesForm = document.getElementById('tables-form');
    const tablesFile = document.getElementById('tables-file');
    const extractTablesBtn = document.getElementById('extract-tables-btn');
    const tablesLoadingSpinner = document.getElementById('tables-loading-spinner');
    const tableSelector = document.getElementById('table-selector');
    const tablesResultsContainer = document.getElementById('tables-results-container');
    const copyTablesJsonBtn = document.getElementById('copy-tables-json-btn');
    
    // Log all DOM elements for debugging
    console.log('DOM Elements:', {
        uploadForm, fileInput, schemaInput, jsonSchemaContainer,
        fieldsBuilder, fieldsContainer, noFieldsMessage, addFieldBtn,
        toggleJsonViewBtn, useChunkingCheckbox, extractBtn, loadingSpinner,
        loadingOverlay, progressContainer, progressBar, progressText,
        resultsContainer, copyJsonBtn
    });
    
    // State variables
    let statusInterval = null;
    let activeDocumentId = null;
    let extractedData = null;
    let extractedTables = null;
    
    // Form submission handler for general extraction
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        console.log("Form submitted");
        
        // Validate file input
        if (!fileInput.files || fileInput.files.length === 0) {
            showAlert('warning', 'Please select a document to upload.');
            return;
        }
        
        // Reset previous results
        resetResults();
        
        // Start loading state
        startLoading();
        
        // Show progress container
        showProgress();
        resetProgress();
        
        // STEP 1: Upload the document
        uploadDocument()
            .then(uploadResult => {
                console.log("Document uploaded successfully", uploadResult);
                
                if (!uploadResult.success) {
                    throw new Error(uploadResult.error || 'Document upload failed');
                }
                
                // Store the active document ID
                activeDocumentId = uploadResult.document_id;
                
                // Update progress
                updateProgress('Document uploaded', 20);
                
                // STEP 2: Start extraction with the schema (if provided)
                return startExtraction(activeDocumentId);
            })
            .then(extractionResult => {
                
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
        
        // Get the schema from the form
        let schema = null;
        
        // If using JSON view, use the schema from the textarea
        if (jsonSchemaContainer.style.display !== 'none') {
            try {
                const schemaText = schemaInput.value.trim();
                if (schemaText) {
                    schema = JSON.parse(schemaText);
                }
            } catch (error) {
                throw new Error('Invalid JSON schema format: ' + error.message);
            }
        } else {
            // Otherwise, build the schema from the fields
            schema = updateSchemaFromFields(true); // get the schema without updating the input
        }
        
        // Create the request body
        const requestBody = {
            document_id: documentId,
            use_chunking: useChunkingCheckbox.checked
        };
        
        // Add schema if provided
        if (schema && Object.keys(schema).length > 0) {
            requestBody.extraction_schema = schema;
        }
        
        // Send extraction request
        return fetch('/api/extract', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        })
        .then(handleResponse);
    }
    
    // Start polling for document status
    function startStatusPolling(documentId) {
        console.log("Starting status polling for document:", documentId);
        stopStatusPolling(); // Clear any existing interval
        
        // Poll immediately and then at intervals
        checkDocumentStatus(documentId);
        statusInterval = setInterval(() => checkDocumentStatus(documentId), 2000);
    }
    
    // Stop polling for document status
    function stopStatusPolling() {
        if (statusInterval) {
            clearInterval(statusInterval);
            statusInterval = null;
        }
    }
    
    // Check document status
    function checkDocumentStatus(documentId) {
        console.log("Checking status for document:", documentId);
        fetch(`/api/status/${documentId}`)
            .then(handleResponse)
            .then(statusData => {
                console.log("Document status:", statusData);
                
                // Update the progress based on status
                updateProgressFromStatus(statusData.status, statusData);
                
                if (statusData.status === 'completed') {
                    // Stop polling and fetch the results
                    stopStatusPolling();
                    console.log("Fetching results for document:", documentId);
                    
                    // Proceed to fetch the results
                    fetchExtractionResults(documentId)
                        .then(result => {
                            console.log("Got extraction results:", result);
                            
                            if (!result.success) {
                                showAlert('danger', 'Extraction failed: ' + (result.error || 'Unknown error'));
                                stopLoading();
                                hideProgress();
                                return;
                            }
                            
                            // Store the extracted data for later use
                            extractedData = result.data;
                            console.log("Extracted data:", extractedData);
                            
                            // Display the results
                            displayResults(result.data);
                            
                            // Update UI state
                            stopLoading();
                            updateProgress('Extraction completed', 100, 'bg-success');
                            
                            // Enable copy button
                            copyJsonBtn.disabled = false;
                            
                            // Show success message
                            showAlert('success', 'Document extraction completed successfully!');
                        })
                        .catch(error => {
                            console.error("Error fetching results:", error);
                            showAlert('danger', 'Error fetching results: ' + error.message);
                            stopLoading();
                            hideProgress();
                        });
                } else if (statusData.status === 'failed') {
                    // Show error and stop polling
                    stopStatusPolling();
                    showAlert('danger', 'Extraction failed: ' + (statusData.error || 'Unknown error'));
                    stopLoading();
                    hideProgress();
                }
                // For 'pending' or 'processing' status, continue polling
            })
            .catch(error => {
                console.error("Error checking status:", error);
                showAlert('danger', 'Error checking status: ' + error.message);
                stopStatusPolling();
                stopLoading();
                hideProgress();
            });
    }
    
    // Fetch extraction results
    function fetchExtractionResults(documentId) {
        console.log("Fetching results for document:", documentId);
        return fetch(`/api/result/${documentId}`)
            .then(handleResponse)
            .then(result => {
                console.log("Raw API response for results:", result);
                return result;
            });
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
                showAlert('success', 'Results copied to clipboard');
            },
            function() {
                showAlert('danger', 'Failed to copy results');
                
                // Fallback copy method
                const textArea = document.createElement('textarea');
                textArea.value = jsonStr;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
            }
        );
    });
    
    // Table extraction form submission handler
    tablesForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Validate file input
        if (!tablesFile.files || tablesFile.files.length === 0) {
            showAlert('warning', 'Please select a PDF document to extract tables from.');
            return;
        }
        
        // Start loading state
        startTablesLoading();
        
        // Prepare form data for upload
        const formData = new FormData();
        formData.append('file', tablesFile.files[0]);
        
        // Send request to extract tables
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
        console.log("Displaying results:", data);
        
        // Check if results container exists
        if (!resultsContainer) {
            console.error("Results container is null");
            return;
        }
        
        // Clear previous results
        resetResults();
        
        // Show the container
        resultsContainer.style.display = 'block';
        
        // Debug the results container's children
        console.log("Results container children:", resultsContainer.childNodes);
        
        // Get pre element for results
        const preElement = document.getElementById('json-output');
        console.log("Pre element for JSON output:", preElement);
        
        if (!preElement) {
            console.error("Error: Could not find element with ID 'json-output'");
            showAlert('danger', 'Error displaying results: UI element not found.');
            
            // Create the element if it doesn't exist
            const newPreElement = document.createElement('pre');
            newPreElement.id = 'json-output';
            newPreElement.className = 'json-display';
            resultsContainer.appendChild(newPreElement);
            
            console.log("Created new pre element:", newPreElement);
            
            // Try again with the new element
            displayResults(data);
            return;
        }
        
        // Store the extracted data for the copy button
        extractedData = data;
        
        // Add a friendly message if all fields are null
        let allFieldsNull = true;
        if (data && typeof data === 'object') {
            allFieldsNull = Object.values(data).every(val => val === null);
        }
        
        if (allFieldsNull && Object.keys(data).length > 0) {
            // Add a friendly message before the JSON
            preElement.innerHTML = `<div class="alert alert-warning mb-3">
                <p><strong>Note:</strong> No specific data could be extracted for the requested fields.</p>
                <p>This may be because:</p>
                <ul>
                    <li>The document doesn't contain the requested information</li>
                    <li>The information format wasn't recognized</li>
                    <li>The extraction model needs more specific field descriptions</li>
                </ul>
                <p>Try again with more specific field descriptions or try different fields.</p>
            </div>`;
            
            // Still show the structure with null values
            const formattedJson = syntaxHighlight(JSON.stringify(data, null, 2));
            preElement.innerHTML += formattedJson;
        } else {
            // Format the data normally
            const formattedJson = syntaxHighlight(JSON.stringify(data, null, 2));
            
            // Add formatted JSON to the results
            preElement.innerHTML = formattedJson;
        }
        console.log("Set inner HTML of pre element");
        
        // Enable the copy button
        copyJsonBtn.disabled = false;
    }
    
    /**
     * Reset the results container to its initial state
     */
    function resetResults() {
        console.log("Resetting results");
        
        // Reset extracted data
        extractedData = null;
        
        // Don't hide the container, just clear its contents
        // resultsContainer.style.display = 'none';
        
        // Clear any previous results
        const preElement = document.getElementById('json-output');
        if (preElement) {
            preElement.innerHTML = '';
            console.log("Cleared pre element content");
        } else {
            console.log("No pre element found during reset");
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
        progressContainer.classList.remove('d-none');
    }
    
    /**
     * Hide progress container
     */
    function hideProgress() {
        progressContainer.classList.add('d-none');
    }
    
    /**
     * Reset progress display
     */
    function resetProgress() {
        progressBar.style.width = '0%';
        progressBar.setAttribute('aria-valuenow', 0);
        progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated';
        progressText.textContent = 'Starting...';
    }
    
    /**
     * Update progress display
     */
    function updateProgress(message, percentage, className = null) {
        progressBar.style.width = percentage + '%';
        progressBar.setAttribute('aria-valuenow', percentage);
        
        if (className) {
            progressBar.className = `progress-bar ${className}`;
        }
        
        progressText.textContent = message;
    }
    
    /**
     * Update progress based on document status
     */
    function updateProgressFromStatus(status, statusData) {
        let percentage = 0;
        let message = '';
        
        switch (status) {
            case 'pending':
                percentage = 30;
                message = 'Waiting for processing to begin...';
                break;
            case 'processing':
                // Calculate progress based on extraction_status
                if (statusData.extraction_status) {
                    const extractionStatuses = statusData.extraction_status;
                    const totalFields = Object.keys(extractionStatuses).length + 1; // +1 for initial upload
                    const completedFields = Object.values(extractionStatuses).filter(s => s === 'completed').length;
                    
                    // Calculate percentage from 30-90%
                    percentage = 30 + (completedFields / totalFields) * 60;
                    
                    if (totalFields > 1) {
                        message = `Processing document: ${completedFields}/${totalFields} fields completed`;
                    } else {
                        message = 'Processing document...';
                    }
                } else {
                    percentage = 50;
                    message = 'Processing document...';
                }
                break;
            case 'completed':
                percentage = 90; // We'll set to 100 after fetching results
                message = 'Extraction completed, fetching results...';
                break;
            case 'failed':
                percentage = 100;
                message = 'Extraction failed: ' + (statusData.error || 'Unknown error');
                updateProgress(message, percentage, 'bg-danger');
                return;
        }
        
        updateProgress(message, percentage);
    }
    
    /**
     * Show an alert message that fades after a few seconds
     */
    function showAlert(type, message) {
        const alertsContainer = document.getElementById('alerts-container');
        
        if (!alertsContainer) {
            console.error('Alerts container not found');
            return;
        }
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        alertsContainer.appendChild(alert);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            try {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            } catch (e) {
                // Fallback if Bootstrap JS not available
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 500);
            }
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
    
    function addField(name = '', description = '') {
        // Create a new field row
        const fieldRow = document.createElement('div');
        fieldRow.className = 'field-row mb-3 border-bottom pb-3';
        
        fieldRow.innerHTML = `
            <div class="row g-2">
                <div class="col-5">
                    <input type="text" class="form-control field-name" placeholder="Field name" value="${name}" />
                </div>
                <div class="col-6">
                    <input type="text" class="form-control field-description" placeholder="Description (optional)" value="${description}" />
                </div>
                <div class="col-1">
                    <button type="button" class="btn btn-outline-danger remove-field-btn">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        `;
        
        // Add remove button functionality
        const removeBtn = fieldRow.querySelector('.remove-field-btn');
        removeBtn.addEventListener('click', function() {
            fieldRow.remove();
            updateFieldDisplay();
        });
        
        // Add the field to the container
        fieldsContainer.appendChild(fieldRow);
    }
    
    function updateFieldDisplay() {
        // Show/hide the no fields message
        const hasFields = fieldsContainer.children.length > 0;
        noFieldsMessage.style.display = hasFields ? 'none' : 'block';
    }
    
    function updateSchemaFromFields(returnOnly = false) {
        // Get all field rows
        const fieldRows = fieldsContainer.querySelectorAll('.field-row');
        
        // Build the schema object
        const fields = [];
        
        fieldRows.forEach(row => {
            const nameInput = row.querySelector('.field-name');
            const descInput = row.querySelector('.field-description');
            
            if (nameInput.value.trim()) {
                const field = {
                    name: nameInput.value.trim()
                };
                
                if (descInput.value.trim()) {
                    field.description = descInput.value.trim();
                }
                
                fields.push(field);
            }
        });
        
        // Create the schema object
        const schema = {
            fields: fields
        };
        
        // Either update the input or just return the value
        if (!returnOnly) {
            schemaInput.value = JSON.stringify(schema, null, 2);
        }
        
        return schema;
    }
    
    function updateFieldsFromSchema() {
        try {
            // Clear existing fields
            fieldsContainer.innerHTML = '';
            
            // Parse the JSON schema
            let schema = null;
            
            try {
                const schemaText = schemaInput.value.trim();
                if (schemaText) {
                    schema = JSON.parse(schemaText);
                }
            } catch (error) {
                showAlert('danger', 'Invalid JSON schema format: ' + error.message);
                return;
            }
            
            // If no schema or no fields, add a default empty field
            if (!schema || !schema.fields || schema.fields.length === 0) {
                addField();
            } else {
                // Add each field from the schema
                schema.fields.forEach(field => {
                    addField(field.name, field.description || '');
                });
            }
            
            // Update field display
            updateFieldDisplay();
            
        } catch (error) {
            console.error('Error updating fields from schema:', error);
            showAlert('danger', 'Error updating fields: ' + error.message);
        }
    }
    
    /**
     * Display table extraction results
     */
    function displayTablesResults(data) {
        // Store the tables data
        extractedTables = data.tables;
        
        // Clear the table selector
        tableSelector.innerHTML = '<option selected disabled>Select a table to view</option>';
        
        // Clear the results container
        tablesResultsContainer.innerHTML = '';
        
        // Enable copy button
        copyTablesJsonBtn.disabled = false;
        
        // If no tables found
        if (!extractedTables || extractedTables.length === 0) {
            tablesResultsContainer.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle me-2"></i>
                    No tables found in the document
                </div>
            `;
            return;
        }
        
        // Show table selector
        tableSelector.classList.remove('d-none');
        
        // Add tables to the selector
        extractedTables.forEach((table, index) => {
            const option = document.createElement('option');
            option.value = index;
            option.textContent = `Table ${index + 1}${table.title ? ': ' + table.title : ''}`;
            tableSelector.appendChild(option);
        });
        
        // Show first table by default
        displayTableDetails(extractedTables[0]);
        
        // Add selector change event
        tableSelector.addEventListener('change', function() {
            const selectedIndex = parseInt(this.value);
            displayTableDetails(extractedTables[selectedIndex]);
        });
    }
    
    /**
     * Display details of a specific table
     */
    function displayTableDetails(tableData) {
        // Clear the results container
        tablesResultsContainer.innerHTML = '';
        
        // Table title
        if (tableData.title) {
            const title = document.createElement('h4');
            title.className = 'mb-3';
            title.textContent = tableData.title;
            tablesResultsContainer.appendChild(title);
        }
        
        // Table data
        if (tableData.data && tableData.data.length > 0) {
            // Render as HTML table
            tablesResultsContainer.innerHTML += renderTableHtml(tableData);
        } else {
            tablesResultsContainer.innerHTML += `
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    This table contains no data
                </div>
            `;
        }
    }
    
    /**
     * Render HTML for a table
     */
    function renderTableHtml(tableData) {
        let html = '<div class="table-responsive"><table class="table table-striped table-bordered">';
        
        // Headers
        if (tableData.headers && tableData.headers.length > 0) {
            html += '<thead><tr>';
            tableData.headers.forEach(header => {
                html += `<th>${header}</th>`;
            });
            html += '</tr></thead>';
        }
        
        // Body
        html += '<tbody>';
        if (tableData.data && tableData.data.length > 0) {
            tableData.data.forEach(row => {
                html += '<tr>';
                row.forEach(cell => {
                    html += `<td>${cell}</td>`;
                });
                html += '</tr>';
            });
        }
        html += '</tbody></table></div>';
        
        return html;
    }
    
    /**
     * Start loading state for table extraction
     */
    function startTablesLoading() {
        tablesLoadingSpinner.classList.remove('d-none');
        extractTablesBtn.disabled = true;
    }
    
    /**
     * Stop loading state for table extraction
     */
    function stopTablesLoading() {
        tablesLoadingSpinner.classList.add('d-none');
        extractTablesBtn.disabled = false;
    }
    
    // Initialize UI
    // Set alerts container to be empty
    const alertsContainer = document.getElementById('alerts-container');
    if (alertsContainer) {
        alertsContainer.innerHTML = '';
    }
    
    // Show fields builder initially, hide JSON input
    jsonSchemaContainer.style.display = 'none';
    fieldsBuilder.style.display = 'block';
    
    // Add default empty field
    addField();
    updateFieldDisplay();
    
    // Log HTML structure of results container for debugging
    console.log("Results container HTML:", resultsContainer ? resultsContainer.innerHTML : "null");
    
    // Check for json-output element
    const jsonOutput = document.getElementById('json-output');
    console.log("JSON output element:", jsonOutput);
    
    // If json-output doesn't exist, create it
    if (!jsonOutput && resultsContainer) {
        const preElement = document.createElement('pre');
        preElement.id = 'json-output';
        preElement.className = 'json-display';
        // Append it to the results container
        resultsContainer.appendChild(preElement);
        console.log("Created json-output element:", preElement);
    }
});
