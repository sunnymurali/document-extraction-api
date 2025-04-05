/**
 * Document Data Extractor
 * Frontend JavaScript for handling document uploads and displaying results
 * Enhanced with asynchronous processing to handle large documents without blocking
 */

document.addEventListener('DOMContentLoaded', function() {
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
    
    // Progress tracking elements (will be created dynamically if not in DOM)
    let progressContainer = document.getElementById('progress-container');
    let progressBar = document.getElementById('extraction-progress');
    let progressText = document.getElementById('progress-text');
    
    // Create progress elements if they don't exist
    if (!progressContainer) {
        progressContainer = document.createElement('div');
        progressContainer.id = 'progress-container';
        progressContainer.className = 'progress-container mt-3 mb-4 d-none';
        
        progressBar = document.createElement('div');
        progressBar.id = 'extraction-progress';
        progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated';
        progressBar.role = 'progressbar';
        progressBar.setAttribute('aria-valuenow', '0');
        progressBar.setAttribute('aria-valuemin', '0');
        progressBar.setAttribute('aria-valuemax', '100');
        progressBar.style.width = '0%';
        
        progressText = document.createElement('div');
        progressText.id = 'progress-text';
        progressText.className = 'text-center mt-2';
        progressText.textContent = 'Starting...';
        
        const progressBarContainer = document.createElement('div');
        progressBarContainer.className = 'progress';
        progressBarContainer.appendChild(progressBar);
        
        progressContainer.appendChild(progressBarContainer);
        progressContainer.appendChild(progressText);
        
        // Insert after the form
        uploadForm.parentNode.insertBefore(progressContainer, uploadForm.nextSibling);
    }
    
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
        // Clear any existing polling
        stopStatusPolling();
        
        // Set up polling interval (check every 2 seconds)
        statusPollingInterval = setInterval(() => {
            checkDocumentStatus(documentId)
                .then(statusResult => {
                    if (!statusResult.success) {
                        throw new Error(statusResult.error || 'Failed to get document status');
                    }
                    
                    // Update progress based on status
                    const status = statusResult.status;
                    updateProgressFromStatus(status, statusResult);
                    
                    // If completed or failed, stop polling and fetch results
                    if (status === 'completed') {
                        stopStatusPolling();
                        
                        // Fetch the extraction results
                        fetchExtractionResults(documentId)
                            .then(resultData => {
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
        return fetch(`/api/status/${documentId}`)
            .then(handleResponse);
    }
    
    // Fetch extraction results
    function fetchExtractionResults(documentId) {
        return fetch(`/api/result/${documentId}`)
            .then(handleResponse);
    }
    
    // Standard response handler
    function handleResponse(response) {
        // First check if the response is ok
        if (!response.ok) {
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
            }
        }
        
        if (progressText) {
            progressText.textContent = `${message} (${percentage}%)`;
        }
    }
    
    /**
     * Update progress based on document status
     */
    function updateProgressFromStatus(status, statusData) {
        let percentage = 0;
        let message = '';
        
        switch (status) {
            case 'pending':
                percentage = 20;
                message = 'Waiting to start';
                break;
            case 'processing':
                // For processing, we'll calculate percentage based on fields if available
                if (statusData.extraction_status && Object.keys(statusData.extraction_status).length > 0) {
                    const totalFields = Object.keys(statusData.extraction_status).length;
                    const completedFields = Object.values(statusData.extraction_status)
                        .filter(s => s === 'completed').length;
                    
                    percentage = 30 + Math.floor((completedFields / totalFields) * 60);
                    message = `Processed ${completedFields} of ${totalFields} fields`;
                } else {
                    percentage = 50;
                    message = 'Processing document';
                }
                break;
            case 'completed':
                percentage = 90;
                message = 'Finalizing results';
                break;
            case 'failed':
                percentage = 100;
                message = 'Processing failed';
                break;
            default:
                percentage = 30;
                message = 'Processing document';
        }
        
        updateProgress(message, percentage, status === 'failed' ? 'bg-danger' : null);
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
            try {
                const bsAlert = new bootstrap.Alert(alertEl);
                bsAlert.close();
            } catch (e) {
                // Fallback if bootstrap is not available
                alertEl.remove();
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

    // Field builder UI
    if (addFieldBtn) {
        addFieldBtn.addEventListener('click', function() {
            addField();
            updateFieldDisplay();
        });
    }

    // Toggle schema JSON view
    if (toggleJsonViewBtn) {
        toggleJsonViewBtn.addEventListener('click', function() {
            jsonSchemaContainer.classList.toggle('d-none');
            fieldsBuilder.classList.toggle('d-none');
            
            if (jsonSchemaContainer.classList.contains('d-none')) {
                toggleJsonViewBtn.textContent = 'Edit as JSON';
                // Update fields from JSON
                updateFieldsFromSchema();
            } else {
                toggleJsonViewBtn.textContent = 'Builder View';
                // Update JSON from fields
                updateSchemaFromFields();
            }
        });
    }

    function addField(name = '', description = '') {
        const fieldId = 'field-' + fieldCount++;
        
        const fieldDiv = document.createElement('div');
        fieldDiv.className = 'field-item mb-3 p-3 border rounded';
        fieldDiv.id = fieldId;
        
        fieldDiv.innerHTML = `
            <div class="row align-items-center">
                <div class="col">
                    <div class="mb-2">
                        <label class="form-label">Field Name</label>
                        <input type="text" class="form-control field-name" value="${name}" placeholder="e.g., invoice_number">
                    </div>
                </div>
                <div class="col-auto">
                    <button type="button" class="btn btn-danger btn-sm remove-field">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            <div class="mb-0">
                <label class="form-label">Description</label>
                <textarea class="form-control field-description" rows="2" placeholder="Describe what should be extracted">${description}</textarea>
            </div>
        `;
        
        // Add event listener for remove button
        fieldDiv.querySelector('.remove-field').addEventListener('click', function() {
            fieldDiv.remove();
            updateFieldDisplay();
            updateSchemaFromFields();
        });
        
        // Add event listeners for input changes
        const inputs = fieldDiv.querySelectorAll('input, textarea');
        inputs.forEach(input => {
            input.addEventListener('input', updateSchemaFromFields);
        });
        
        // Append to the container
        fieldsContainer.appendChild(fieldDiv);
        
        return fieldDiv;
    }
    
    function updateFieldDisplay() {
        const fieldItems = fieldsContainer.querySelectorAll('.field-item');
        
        if (fieldItems.length === 0) {
            noFieldsMessage.classList.remove('d-none');
        } else {
            noFieldsMessage.classList.add('d-none');
        }
        
        // Update the schema
        updateSchemaFromFields();
    }
    
    function updateSchemaFromFields() {
        const fieldItems = fieldsContainer.querySelectorAll('.field-item');
        const fields = [];
        
        fieldItems.forEach(item => {
            const nameInput = item.querySelector('.field-name');
            const descInput = item.querySelector('.field-description');
            
            if (nameInput.value.trim()) {
                fields.push({
                    name: nameInput.value.trim(),
                    description: descInput.value.trim()
                });
            }
        });
        
        const schema = { fields };
        schemaInput.value = JSON.stringify(schema, null, 2);
    }
    
    function updateFieldsFromSchema() {
        try {
            if (!schemaInput.value.trim()) {
                return;
            }
            
            const schema = JSON.parse(schemaInput.value);
            
            // Clear existing fields
            fieldsContainer.innerHTML = '';
            fieldCount = 0;
            
            // Add fields from schema
            if (schema.fields && Array.isArray(schema.fields)) {
                schema.fields.forEach(field => {
                    addField(field.name || '', field.description || '');
                });
            }
            
            updateFieldDisplay();
            
        } catch (e) {
            console.error('Error parsing schema:', e);
            showAlert('danger', 'Invalid schema format: ' + e.message);
        }
    }
    
    // Initialize fields builder if schema is provided
    updateFieldsFromSchema();

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
                // Check if response is HTML
                if (response.headers.get('content-type')?.includes('text/html')) {
                    return response.text().then(html => {
                        throw new Error('Server returned HTML instead of JSON. This typically indicates a server error or authorization problem.');
                    });
                }
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
            
            // Show more user-friendly error message for common errors
            if (error.message.includes('timed out') || error.message.includes('not in JSON format')) {
                showAlert('danger', 'The table extraction process timed out. Please try with a smaller PDF document or fewer pages.');
            } else if (error.message.includes('Unexpected token')) {
                showAlert('danger', 'Failed to parse server response. This usually indicates an API configuration issue with Azure OpenAI.');
            } else if (error.message.includes('HTML instead of JSON')) {
                showAlert('danger', 'Authentication error with Azure OpenAI. Please check your API credentials.');
            } else {
                showAlert('danger', 'Failed to process document: ' + error.message);
            }
            
            // Reset table results area
            tablesResultsContainer.innerHTML = `
                <div class="alert alert-danger">
                    <h4 class="alert-heading">Table Extraction Failed</h4>
                    <p class="mb-0">The document processing may have timed out because:</p>
                    <ul>
                        <li>The PDF is too large or contains too many pages</li>
                        <li>The tables are too complex for extraction</li>
                        <li>There was a network error during processing</li>
                    </ul>
                    <p>Try with a smaller document or fewer pages.</p>
                </div>
            `;
        })
        .finally(() => {
            stopTablesLoading();
        });
    });

    /**
     * Display table extraction results
     */
    function displayTablesResults(data) {
        // Clear previous results
        tablesResultsContainer.innerHTML = '';
        tableSelector.innerHTML = '';
        
        if (data.success && data.tables && data.tables.length > 0) {
            // Create table selector options
            tableSelector.innerHTML = '<option value="" selected disabled>Select a table to view</option>';
            
            data.tables.forEach((table, index) => {
                const option = document.createElement('option');
                option.value = index;
                option.textContent = `Table ${index + 1}${table.caption ? ': ' + table.caption.substring(0, 30) : ''}`;
                tableSelector.appendChild(option);
            });
            
            // Show table selector
            tableSelector.classList.remove('d-none');
            
            // Display processing summary
            tablesResultsContainer.innerHTML = `
                <div class="alert alert-info mb-3">
                    <h5>Processing Results</h5>
                    <p>Found ${data.tables.length} tables in ${data.pages_processed} pages. Select a table from the dropdown to view details.</p>
                </div>
                <div id="table-details"></div>
            `;
            
            // Set up event listener for table selection
            tableSelector.addEventListener('change', function() {
                const selectedIndex = this.value;
                if (selectedIndex !== '') {
                    displayTableDetails(data.tables[selectedIndex]);
                }
            });
        } else if (data.success && (!data.tables || data.tables.length === 0)) {
            // No tables found
            tablesResultsContainer.innerHTML = `
                <div class="alert alert-warning">
                    <h4 class="alert-heading">No Tables Found</h4>
                    <p>No tables were detected in the document. This might be because:</p>
                    <ul>
                        <li>The document doesn't contain any tables</li>
                        <li>Tables in the document are not structured in a way that can be recognized</li>
                        <li>The PDF may contain scanned images of tables rather than actual table structures</li>
                    </ul>
                </div>
            `;
            
            // Hide table selector
            tableSelector.classList.add('d-none');
        } else {
            // Error case
            tablesResultsContainer.innerHTML = `
                <div class="alert alert-danger">
                    <h4 class="alert-heading">Extraction Failed</h4>
                    <p>${data.error || 'An unknown error occurred during table extraction'}</p>
                </div>
            `;
            
            // Hide table selector
            tableSelector.classList.add('d-none');
        }
    }

    /**
     * Display details of a specific table
     */
    function displayTableDetails(tableData) {
        const tableDetails = document.getElementById('table-details');
        
        // Create the table details view
        let detailsHtml = `
            <div class="card mb-4">
                <div class="card-header">
                    <h3 class="card-title h5 mb-0">${tableData.caption || 'Table Details'}</h3>
                </div>
                <div class="card-body">
        `;
        
        // Add metadata
        detailsHtml += `
            <div class="mb-3">
                <h6>Table Information</h6>
                <ul class="list-unstyled">
                    <li><strong>Page:</strong> ${tableData.page_number || 'Unknown'}</li>
                    <li><strong>Rows:</strong> ${tableData.rows?.length || 0}</li>
                    <li><strong>Columns:</strong> ${tableData.headers?.length || 0}</li>
                </ul>
            </div>
        `;
        
        // Render table if we have rows and columns
        if (tableData.rows && tableData.rows.length > 0) {
            detailsHtml += renderTableHtml(tableData);
        } else {
            detailsHtml += `
                <div class="alert alert-warning">
                    <p>Table structure could not be properly extracted.</p>
                </div>
            `;
        }
        
        // Add raw data section
        detailsHtml += `
            <div class="mt-4">
                <h6>Raw Data</h6>
                <pre class="json-display">${syntaxHighlight(JSON.stringify(tableData, null, 2))}</pre>
            </div>
        `;
        
        // Close the card
        detailsHtml += `
                </div>
            </div>
        `;
        
        // Update the table details container
        tableDetails.innerHTML = detailsHtml;
    }

    /**
     * Render HTML for a table
     */
    function renderTableHtml(tableData) {
        let tableHtml = '<div class="table-responsive"><table class="table table-bordered table-striped">';
        
        // Add headers if available
        if (tableData.headers && tableData.headers.length > 0) {
            tableHtml += '<thead><tr>';
            tableData.headers.forEach(header => {
                tableHtml += `<th>${header}</th>`;
            });
            tableHtml += '</tr></thead>';
        }
        
        // Add body
        tableHtml += '<tbody>';
        
        if (tableData.rows && tableData.rows.length > 0) {
            tableData.rows.forEach(row => {
                tableHtml += '<tr>';
                
                if (Array.isArray(row)) {
                    row.forEach(cell => {
                        tableHtml += `<td>${cell}</td>`;
                    });
                } else if (typeof row === 'object') {
                    // If rows are objects with named properties, use headers to determine order
                    if (tableData.headers && tableData.headers.length > 0) {
                        tableData.headers.forEach(header => {
                            tableHtml += `<td>${row[header] || ''}</td>`;
                        });
                    } else {
                        // If no headers, just show the values
                        Object.values(row).forEach(value => {
                            tableHtml += `<td>${value}</td>`;
                        });
                    }
                }
                
                tableHtml += '</tr>';
            });
        }
        
        tableHtml += '</tbody></table></div>';
        
        return tableHtml;
    }

    /**
     * Start loading state for table extraction
     */
    function startTablesLoading() {
        extractTablesBtn.disabled = true;
        tablesLoadingSpinner.classList.remove('d-none');
        // Reset table selector
        tableSelector.innerHTML = '';
        tableSelector.classList.add('d-none');
    }

    /**
     * Stop loading state for table extraction
     */
    function stopTablesLoading() {
        extractTablesBtn.disabled = false;
        tablesLoadingSpinner.classList.add('d-none');
    }

    // Copy tables JSON button
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
});
