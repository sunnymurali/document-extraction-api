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
        formData.append('file', fileInput.files[0]);
        
        return fetch('/api/upload', {
            method: 'POST',
            body: formData
        })
        .then(handleResponse);
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
                                console.log("Extraction results:", resultData);
                                
                                // Store the data for copy functionality
                                extractedData = resultData;
                                
                                // Display results
                                displayResults(resultData);
                                
                                // Enable copy button
                                copyJsonBtn.disabled = false;
                                
                                showAlert('success', 'Document processed successfully');
                                updateProgress('Completed', 100);
                                
                                // Hide progress after a delay
                                setTimeout(() => {
                                    hideProgress();
                                }, 2000);
                            })
                            .catch(error => {
                                console.error('Error fetching results:', error);
                                showAlert('danger', 'Error fetching results: ' + error.message);
                            })
                            .finally(() => {
                                stopLoading();
                            });
                    } else if (status === 'failed') {
                        stopStatusPolling();
                        showAlert('danger', statusResult.error || 'Document processing failed');
                        updateProgress('Failed', 100, 'bg-danger');
                        stopLoading();
                    }
                })
                .catch(error => {
                    console.error('Error polling status:', error);
                    stopStatusPolling();
                    showAlert('danger', 'Error checking status: ' + error.message);
                    stopLoading();
                });
        }, 2000);
    }
    
    // Stop polling for document status
    function stopStatusPolling() {
        if (statusPollingInterval) {
            clearInterval(statusPollingInterval);
            statusPollingInterval = null;
        }
    }
    
    // Check document status
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
    
    /**
     * Display extraction results in the results container
     */
    function displayResults(data) {
        // Clear previous results
        resultsContainer.innerHTML = '';
        
        if (data.success && data.data) {
            // Show chunking information if available
            let chunkingInfo = '';
            if (data.chunking_info) {
                if (data.chunking_info.used) {
                    chunkingInfo = `
                        <div class="alert alert-info mb-3">
                            <h5>Document Processing Information</h5>
                            <p>Document was processed using chunking: ${data.chunking_info.chunks_processed} of ${data.chunking_info.total_chunks} chunks processed.</p>
                        </div>
                    `;
                } else {
                    chunkingInfo = `
                        <div class="alert alert-info mb-3">
                            <p>Document was processed as a single chunk (chunking disabled or not needed).</p>
                        </div>
                    `;
                }
            }
            
            // Create results display
            const resultHtml = `
                ${chunkingInfo}
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
     * Show progress container
     */
    function showProgress() {
        if (progressContainer) {
            progressContainer.classList.remove('d-none');
        }
    }
    
    /**
     * Hide progress container
     */
    function hideProgress() {
        if (progressContainer) {
            progressContainer.classList.add('d-none');
        }
    }
    
    /**
     * Reset progress display
     */
    function resetProgress() {
        if (progressBar) {
            progressBar.style.width = '0%';
            progressBar.setAttribute('aria-valuenow', 0);
            progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated';
        }
        if (progressText) {
            progressText.textContent = 'Starting...';
        }
    }
    
    /**
     * Update progress display
     */
    function updateProgress(message, percentage, className = null) {
        if (progressBar) {
            progressBar.style.width = `${percentage}%`;
            progressBar.setAttribute('aria-valuenow', percentage);
            
            if (className) {
                progressBar.className = `progress-bar ${className}`;
            } else {
                progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated';
            }
        }
        if (progressText) {
            progressText.textContent = message;
        }
    }
    
    /**
     * Update progress based on document status
     */
    function updateProgressFromStatus(status, statusData) {
        switch (status) {
            case 'pending':
                updateProgress('Waiting to start processing...', 20);
                break;
            case 'processing':
                // Calculate progress based on extraction_status if available
                if (statusData.extraction_status) {
                    const totalFields = Object.keys(statusData.extraction_status).length;
                    if (totalFields > 0) {
                        const completedFields = Object.values(statusData.extraction_status)
                            .filter(s => s === 'completed').length;
                        const percent = 30 + Math.floor((completedFields / totalFields) * 60);
                        updateProgress(`Processing document (${completedFields}/${totalFields} fields completed)`, percent);
                    } else {
                        updateProgress('Processing document...', 50);
                    }
                } else {
                    updateProgress('Processing document...', 50);
                }
                break;
            case 'completed':
                updateProgress('Document processing completed', 100, 'bg-success');
                break;
            case 'failed':
                updateProgress('Document processing failed', 100, 'bg-danger');
                break;
            default:
                updateProgress('Unknown status', 50);
                break;
        }
    }
    
    /**
     * Show an alert message that fades after a few seconds
     */
    function showAlert(type, message) {
        // Create alert container if it doesn't exist
        let alertContainer = document.getElementById('alert-container');
        if (!alertContainer) {
            alertContainer = document.createElement('div');
            alertContainer.id = 'alert-container';
            alertContainer.className = 'alert-container position-fixed top-0 start-50 translate-middle-x p-3';
            alertContainer.style.zIndex = '1050';
            document.body.appendChild(alertContainer);
        }
        
        // Create alert
        const alertId = 'alert-' + Date.now();
        const alertHtml = `
            <div id="${alertId}" class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        
        // Add alert to container
        alertContainer.insertAdjacentHTML('beforeend', alertHtml);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            const alert = document.getElementById(alertId);
            if (alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    }
    
    /**
     * Syntax highlight JSON for display
     */
    function syntaxHighlight(json) {
        if (!json) return '';
        
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
    
    // Field builder functionality
    if (addFieldBtn) {
        addFieldBtn.addEventListener('click', function() {
            addField();
            updateFieldDisplay();
        });
    }
    
    function addField(name = '', description = '') {
        const fieldId = `field-${fieldCount++}`;
        const fieldHtml = `
            <div class="field-item card mb-2" id="${fieldId}">
                <div class="card-body p-3">
                    <div class="row g-2">
                        <div class="col-md-5">
                            <label class="form-label" for="${fieldId}-name">Field Name</label>
                            <input type="text" class="form-control field-name" id="${fieldId}-name" value="${name}" placeholder="e.g. total_amount">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label" for="${fieldId}-desc">Description</label>
                            <input type="text" class="form-control field-desc" id="${fieldId}-desc" value="${description}" placeholder="e.g. The total invoice amount">
                        </div>
                        <div class="col-md-1 d-flex align-items-end">
                            <button type="button" class="btn btn-outline-danger remove-field-btn" data-field-id="${fieldId}">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        fieldsContainer.insertAdjacentHTML('beforeend', fieldHtml);
        
        // Add event listener to the remove button
        const removeBtn = fieldsContainer.querySelector(`#${fieldId} .remove-field-btn`);
        removeBtn.addEventListener('click', function() {
            const fieldId = this.getAttribute('data-field-id');
            const fieldElement = document.getElementById(fieldId);
            if (fieldElement) {
                fieldElement.remove();
                updateFieldDisplay();
            }
        });
        
        // Add input change listeners
        const nameInput = fieldsContainer.querySelector(`#${fieldId}-name`);
        const descInput = fieldsContainer.querySelector(`#${fieldId}-desc`);
        
        nameInput.addEventListener('input', updateSchemaFromFields);
        descInput.addEventListener('input', updateSchemaFromFields);
        
        return fieldId;
    }
    
    function updateFieldDisplay() {
        const hasFields = fieldsContainer.querySelectorAll('.field-item').length > 0;
        
        if (hasFields) {
            noFieldsMessage.classList.add('d-none');
        } else {
            noFieldsMessage.classList.remove('d-none');
        }
        
        updateSchemaFromFields();
    }
    
    function updateSchemaFromFields() {
        const fields = [];
        
        fieldsContainer.querySelectorAll('.field-item').forEach(field => {
            const nameInput = field.querySelector('.field-name');
            const descInput = field.querySelector('.field-desc');
            
            if (nameInput.value.trim()) {
                fields.push({
                    name: nameInput.value.trim(),
                    description: descInput.value.trim()
                });
            }
        });
        
        const schema = {
            fields: fields
        };
        
        schemaInput.value = JSON.stringify(schema, null, 2);
    }
    
    function updateFieldsFromSchema() {
        try {
            if (!schemaInput.value.trim()) {
                // Clear fields if schema is empty
                fieldsContainer.innerHTML = '';
                updateFieldDisplay();
                return;
            }
            
            const schema = JSON.parse(schemaInput.value);
            
            if (!schema.fields || !Array.isArray(schema.fields)) {
                return;
            }
            
            // Clear existing fields
            fieldsContainer.innerHTML = '';
            
            // Add fields from schema
            schema.fields.forEach(field => {
                addField(field.name || '', field.description || '');
            });
            
            updateFieldDisplay();
        } catch (e) {
            console.error('Error parsing schema JSON:', e);
        }
    }
    
    // Toggle between JSON and field builder
    if (toggleJsonViewBtn) {
        toggleJsonViewBtn.addEventListener('click', function() {
            const isJsonView = !jsonSchemaContainer.classList.contains('d-none');
            
            if (isJsonView) {
                // Switch to field builder view
                jsonSchemaContainer.classList.add('d-none');
                fieldsBuilder.classList.remove('d-none');
                toggleJsonViewBtn.textContent = 'Edit as JSON';
                
                // Update fields from JSON
                updateFieldsFromSchema();
            } else {
                // Switch to JSON view
                jsonSchemaContainer.classList.remove('d-none');
                fieldsBuilder.classList.add('d-none');
                toggleJsonViewBtn.textContent = 'Visual Editor';
                
                // Update JSON from fields
                updateSchemaFromFields();
            }
        });
    }
    
    // Table extraction form
    if (tablesForm) {
        tablesForm.addEventListener('submit', function(event) {
            event.preventDefault();
            
            // Validate file selection
            if (!tablesFileInput.files || tablesFileInput.files.length === 0) {
                showAlert('danger', 'Please select a PDF file to extract tables from');
                return;
            }
            
            // Start loading state
            startTablesLoading();
            
            // Prepare form data
            const formData = new FormData();
            formData.append('file', tablesFileInput.files[0]);
            
            // Send request
            fetch('/api/extract-tables', {
                method: 'POST',
                body: formData
            })
            .then(handleResponse)
            .then(data => {
                // Display results
                displayTablesResults(data);
                
                // Enable copy button
                copyTablesJsonBtn.disabled = false;
                
                if (data.success) {
                    showAlert('success', 'Tables extracted successfully');
                } else {
                    showAlert('warning', data.error || 'No tables could be extracted from the document');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('danger', 'Error: ' + error.message);
                
                // Reset display
                tablesResultsContainer.innerHTML = `
                    <div class="alert alert-danger">
                        <h4 class="alert-heading">Extraction Failed</h4>
                        <p>${error.message}</p>
                    </div>
                `;
            })
            .finally(() => {
                stopTablesLoading();
            });
        });
    }
    
    // Copy tables JSON button
    if (copyTablesJsonBtn) {
        copyTablesJsonBtn.addEventListener('click', function() {
            // Get current table selector value
            const tableId = tableSelector.value;
            const tableData = window.extractedTables ? window.extractedTables[tableId] : null;
            
            if (!tableData && !window.extractedTables) {
                showAlert('warning', 'No table data available to copy');
                return;
            }
            
            // Copy either the selected table or all tables
            const jsonStr = tableData ? 
                JSON.stringify(tableData, null, 2) : 
                JSON.stringify(window.extractedTables, null, 2);
            
            navigator.clipboard.writeText(jsonStr).then(
                function() {
                    showAlert('info', 'Table data copied to clipboard');
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
    }
    
    /**
     * Display table extraction results
     */
    function displayTablesResults(data) {
        // Clear previous results
        tablesResultsContainer.innerHTML = '';
        tableSelector.innerHTML = '<option selected disabled>Select a table to view</option>';
        tableSelector.classList.add('d-none');
        
        if (data.success && data.tables && data.tables.length > 0) {
            // Store tables in global variable for copy functionality
            window.extractedTables = {};
            data.tables.forEach((table, index) => {
                window.extractedTables[`table-${index}`] = table;
                
                // Add option to table selector
                tableSelector.insertAdjacentHTML('beforeend', `
                    <option value="table-${index}">Table ${index + 1}</option>
                `);
            });
            
            // Show table selector if more than one table
            if (data.tables.length > 1) {
                tableSelector.classList.remove('d-none');
                tableSelector.addEventListener('change', function() {
                    const tableId = this.value;
                    displayTableDetails(window.extractedTables[tableId]);
                });
                
                // Display overview
                tablesResultsContainer.innerHTML = `
                    <div class="alert alert-info">
                        <h5>${data.tables.length} tables found in document</h5>
                        <p>Select a table from the dropdown to view details</p>
                    </div>
                `;
            } else {
                // Display the single table
                displayTableDetails(data.tables[0]);
            }
        } else {
            // No tables found or error
            tablesResultsContainer.innerHTML = `
                <div class="alert alert-warning">
                    <h4 class="alert-heading">No Tables Found</h4>
                    <p>${data.error || 'No tables could be extracted from the document'}</p>
                </div>
            `;
        }
    }
    
    /**
     * Display details of a specific table
     */
    function displayTableDetails(tableData) {
        if (!tableData) return;
        
        const tableHtml = renderTableHtml(tableData);
        
        tablesResultsContainer.innerHTML = `
            <div class="card mb-3">
                <div class="card-header">
                    <h5 class="card-title mb-0">Table Preview</h5>
                </div>
                <div class="card-body table-responsive">
                    ${tableHtml}
                </div>
            </div>
            <div class="card">
                <div class="card-header">
                    <h5 class="card-title mb-0">Table Data (JSON)</h5>
                </div>
                <div class="card-body">
                    <pre class="json-display">${syntaxHighlight(JSON.stringify(tableData, null, 2))}</pre>
                </div>
            </div>
        `;
    }
    
    /**
     * Render HTML for a table
     */
    function renderTableHtml(tableData) {
        if (!tableData || !tableData.data || !tableData.data.length) {
            return '<div class="alert alert-warning">No data available for this table</div>';
        }
        
        const headers = tableData.headers || [];
        const rows = tableData.data;
        
        let tableHtml = '<table class="table table-bordered table-striped">';
        
        // Add headers if available
        if (headers.length > 0) {
            tableHtml += '<thead><tr>';
            headers.forEach(header => {
                tableHtml += `<th>${header}</th>`;
            });
            tableHtml += '</tr></thead>';
        }
        
        // Add body
        tableHtml += '<tbody>';
        rows.forEach(row => {
            tableHtml += '<tr>';
            if (Array.isArray(row)) {
                row.forEach(cell => {
                    tableHtml += `<td>${cell}</td>`;
                });
            } else {
                // Handle non-array rows (shouldn't happen with proper data)
                tableHtml += `<td>${JSON.stringify(row)}</td>`;
            }
            tableHtml += '</tr>';
        });
        tableHtml += '</tbody></table>';
        
        return tableHtml;
    }
    
    /**
     * Start loading state for table extraction
     */
    function startTablesLoading() {
        extractTablesBtn.disabled = true;
        tablesLoadingSpinner.classList.remove('d-none');
    }
    
    /**
     * Stop loading state for table extraction
     */
    function stopTablesLoading() {
        extractTablesBtn.disabled = false;
        tablesLoadingSpinner.classList.add('d-none');
    }
    
    // Add initial field if no fields are defined
    if (fieldsContainer && fieldsContainer.children.length === 0) {
        updateFieldDisplay();
    }
});
