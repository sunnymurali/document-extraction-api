/**
 * Document Data Extraction Frontend
 */

document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('file-input');
    const documentStatus = document.getElementById('document-status');
    const fieldsContainer = document.getElementById('fields-container');
    const fieldsList = document.getElementById('fields-list');
    const noFieldsMessage = document.getElementById('no-fields-message');
    const addFieldBtn = document.getElementById('add-field-btn');
    const extractButton = document.getElementById('extract-button');
    const extractionStatus = document.getElementById('extraction-status');
    const fieldStatusContainer = document.getElementById('field-status-container');
    const resultsContainer = document.getElementById('results-container');
    const jsonOutput = document.getElementById('json-output');
    const clearResultsBtn = document.getElementById('clear-results');
    const errorContainer = document.getElementById('error-container');
    const loadingIndicator = document.getElementById('loading-indicator');

    // Current document and extraction state
    let currentDocumentId = null;
    let currentTaskId = null;
    let extractionTimer = null;
    let documentStatusTimer = null;

    // Hide error container initially
    errorContainer.style.display = 'none';

    /**
     * Upload a document
     */
    uploadForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        
        const file = fileInput.files[0];
        if (!file) {
            showError('Please select a file to upload');
            return;
        }

        try {
            toggleLoading(true);
            
            // Reset UI
            clearExtractionUI();
            
            // Upload the document
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch('/documents/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (!response.ok || !data.success) {
                showError(data.error || 'Failed to upload document');
                return;
            }
            
            currentDocumentId = data.document_id;
            
            // Update document status
            updateDocumentStatus(currentDocumentId, {
                status: data.indexing_status || 'pending',
                message: 'Document uploaded successfully. Indexing in progress...',
                file_name: file.name
            });
            
            // Start polling for document status
            checkDocumentStatus(currentDocumentId);
            
        } catch (error) {
            showError(`Error uploading document: ${error.message}`);
        } finally {
            toggleLoading(false);
        }
    });

    /**
     * Check document indexing status
     */
    async function checkDocumentStatus(documentId) {
        clearTimeout(documentStatusTimer);
        
        try {
            const response = await fetch(`/documents/${documentId}/status`);
            const data = await response.json();
            
            if (!response.ok) {
                showError(data.error || 'Failed to check document status');
                return;
            }
            
            updateDocumentStatus(documentId, data);
            
            // If still indexing, poll again after a delay
            if (data.status === 'indexing' || data.status === 'pending') {
                documentStatusTimer = setTimeout(() => checkDocumentStatus(documentId), 2000);
            } else if (data.status === 'indexed') {
                // Enable extraction when document is indexed
                enableExtractionControls(documentId);
            }
            
        } catch (error) {
            showError(`Error checking document status: ${error.message}`);
        }
    }

    /**
     * Update document status in the UI
     */
    function updateDocumentStatus(documentId, data) {
        if (!data) return;
        
        let statusClass = '';
        switch (data.status) {
            case 'pending':
                statusClass = 'status-pending';
                break;
            case 'indexing':
                statusClass = 'status-indexing';
                break;
            case 'indexed':
                statusClass = 'status-indexed';
                break;
            case 'failed':
                statusClass = 'status-failed';
                break;
            default:
                statusClass = '';
        }
        
        const fileName = data.file_name || 'Document';
        
        documentStatus.innerHTML = `
            <div class="mb-2">
                <strong>File:</strong> ${fileName}
            </div>
            <div>
                <strong>Status:</strong> 
                <span class="status ${statusClass}">${data.status}</span>
            </div>
            <div class="mt-2 text-secondary">
                ${data.message || ''}
            </div>
        `;
    }

    /**
     * Enable extraction controls when document is ready
     */
    function enableExtractionControls(documentId) {
        fieldsContainer.style.display = 'block';
        extractButton.disabled = false;
        
        // Clear any previous fields
        fieldsList.innerHTML = '';
        if (fieldsList.children.length === 0) {
            noFieldsMessage.style.display = 'block';
        } else {
            noFieldsMessage.style.display = 'none';
        }
        
        // Reset extraction results
        extractionStatus.innerHTML = '';
        fieldStatusContainer.innerHTML = '';
        jsonOutput.textContent = '';
        jsonOutput.classList.add('d-none');
    }

    /**
     * Add a field to extract
     */
    addFieldBtn.addEventListener('click', () => {
        // Hide no fields message
        noFieldsMessage.style.display = 'none';
        
        const fieldId = `field-${Date.now()}`;
        const fieldItem = document.createElement('div');
        fieldItem.className = 'field-item card p-3 mb-3';
        fieldItem.id = fieldId;
        
        fieldItem.innerHTML = `
            <button type="button" class="btn-close remove-field" aria-label="Remove field"></button>
            <div class="mb-3">
                <label for="${fieldId}-name" class="form-label">Field Name</label>
                <input type="text" class="form-control field-name" id="${fieldId}-name" placeholder="e.g., revenue, company_name, etc.">
            </div>
            <div class="mb-0">
                <label for="${fieldId}-description" class="form-label">Description (helps AI understand what to extract)</label>
                <textarea class="form-control field-description" id="${fieldId}-description" rows="2" placeholder="e.g., The total annual revenue in USD for the fiscal year"></textarea>
            </div>
        `;
        
        // Add remove button functionality
        const removeBtn = fieldItem.querySelector('.remove-field');
        removeBtn.addEventListener('click', () => {
            fieldItem.remove();
            if (fieldsList.children.length === 0) {
                noFieldsMessage.style.display = 'block';
            }
        });
        
        fieldsList.appendChild(fieldItem);
        
        // Enable extract button if there are fields and a document
        extractButton.disabled = !(currentDocumentId && fieldsList.children.length > 0);
    });

    /**
     * Get all fields from the UI
     */
    function getFields() {
        const fields = [];
        const fieldItems = fieldsList.querySelectorAll('.field-item');
        
        fieldItems.forEach(item => {
            const nameInput = item.querySelector('.field-name');
            const descInput = item.querySelector('.field-description');
            
            const name = nameInput.value.trim();
            const description = descInput.value.trim();
            
            if (name) {
                fields.push({
                    name: name,
                    description: description || name
                });
            }
        });
        
        return fields;
    }

    /**
     * Start data extraction
     */
    extractButton.addEventListener('click', async () => {
        if (!currentDocumentId) {
            showError('No document selected');
            return;
        }
        
        const fields = getFields();
        if (fields.length === 0) {
            showError('Please add at least one field to extract');
            return;
        }
        
        try {
            toggleLoading(true);
            
            // Reset extraction results
            extractionStatus.innerHTML = '';
            fieldStatusContainer.innerHTML = '';
            jsonOutput.textContent = '';
            jsonOutput.classList.add('d-none');
            
            // Create extraction request
            const extractionData = {
                document_id: currentDocumentId,
                fields: fields
            };
            
            const response = await fetch('/documents/extract', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(extractionData)
            });
            
            const data = await response.json();
            
            if (!response.ok || !data.success) {
                showError(data.error || 'Failed to start extraction');
                return;
            }
            
            // Update UI with extraction task info
            currentTaskId = data.task_id;
            extractionStatus.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-cog fa-spin me-2"></i>
                    ${data.message || 'Extraction in progress...'}
                </div>
            `;
            
            // Initialize field status display
            fieldStatusContainer.innerHTML = '';
            fields.forEach(field => {
                const fieldStatusDiv = document.createElement('div');
                fieldStatusDiv.id = `field-status-${field.name}`;
                fieldStatusDiv.className = 'field-status card card-body bg-secondary bg-opacity-10';
                
                fieldStatusDiv.innerHTML = `
                    <div class="d-flex justify-content-between">
                        <strong>${field.name}</strong>
                        <span class="badge bg-warning">pending</span>
                    </div>
                `;
                
                fieldStatusContainer.appendChild(fieldStatusDiv);
            });
            
            // Start polling for extraction status
            checkExtractionStatus(currentTaskId);
            
        } catch (error) {
            showError(`Error starting extraction: ${error.message}`);
        } finally {
            toggleLoading(false);
        }
    });

    /**
     * Check extraction status
     */
    async function checkExtractionStatus(taskId) {
        clearTimeout(extractionTimer);
        
        try {
            const response = await fetch(`/tasks/${taskId}/status`);
            const data = await response.json();
            
            if (!response.ok) {
                showError(data.error || 'Failed to check extraction status');
                return;
            }
            
            updateExtractionStatus(taskId, data);
            
            // If still processing, poll again after a delay
            if (!data.completed) {
                extractionTimer = setTimeout(() => checkExtractionStatus(taskId), 2000);
            } else {
                // Get final results when complete
                getExtractionResult(taskId);
            }
            
        } catch (error) {
            showError(`Error checking extraction status: ${error.message}`);
        }
    }

    /**
     * Update extraction status in the UI
     */
    function updateExtractionStatus(taskId, data) {
        if (!data) return;
        
        // Update overall status
        let statusMessage = '';
        if (data.completed) {
            statusMessage = 'Extraction completed';
            extractionStatus.innerHTML = `
                <div class="alert alert-success">
                    <i class="fas fa-check-circle me-2"></i>
                    ${statusMessage}
                </div>
            `;
        } else {
            statusMessage = data.message || 'Extraction in progress...';
            extractionStatus.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-cog fa-spin me-2"></i>
                    ${statusMessage}
                </div>
            `;
        }
        
        // Update individual field statuses
        if (data.fields && Array.isArray(data.fields)) {
            data.fields.forEach(field => {
                const fieldStatusEl = document.getElementById(`field-status-${field.field_name}`);
                if (!fieldStatusEl) return;
                
                let badgeClass = 'bg-warning'; // default
                if (field.status === 'completed') {
                    badgeClass = 'bg-success';
                } else if (field.status === 'processing') {
                    badgeClass = 'bg-info';
                } else if (field.status === 'failed') {
                    badgeClass = 'bg-danger';
                }
                
                fieldStatusEl.innerHTML = `
                    <div class="d-flex justify-content-between">
                        <strong>${field.field_name}</strong>
                        <span class="badge ${badgeClass}">${field.status}</span>
                    </div>
                    ${field.error ? `<div class="text-danger mt-2">${field.error}</div>` : ''}
                `;
            });
        }
    }

    /**
     * Get final extraction result
     */
    async function getExtractionResult(taskId) {
        try {
            toggleLoading(true);
            
            const response = await fetch(`/tasks/${taskId}/result`);
            const data = await response.json();
            
            if (!response.ok) {
                showError(data.error || 'Failed to get extraction results');
                return;
            }
            
            displayExtractionResult(data);
            
        } catch (error) {
            showError(`Error getting extraction results: ${error.message}`);
        } finally {
            toggleLoading(false);
        }
    }

    /**
     * Display extraction result
     */
    function displayExtractionResult(data) {
        if (!data || !data.results) {
            jsonOutput.textContent = 'No results found';
            jsonOutput.classList.remove('d-none');
            return;
        }
        
        // Format and display JSON result
        const formattedJson = JSON.stringify(data.results, null, 2);
        jsonOutput.textContent = formattedJson;
        jsonOutput.classList.remove('d-none');
        
        // Scroll to results
        jsonOutput.scrollIntoView({ behavior: 'smooth' });
    }

    /**
     * Clear results
     */
    clearResultsBtn.addEventListener('click', () => {
        clearExtractionUI();
    });

    /**
     * Clear extraction UI
     */
    function clearExtractionUI() {
        // Clear timers
        clearTimeout(extractionTimer);
        
        // Reset extraction state
        currentTaskId = null;
        
        // Clear UI
        extractionStatus.innerHTML = '';
        fieldStatusContainer.innerHTML = '';
        jsonOutput.textContent = '';
        jsonOutput.classList.add('d-none');
        
        // Show empty state
        const emptyState = document.createElement('div');
        emptyState.className = 'text-center py-5 text-secondary';
        emptyState.innerHTML = `
            <i class="fas fa-file-alt fa-3x mb-3"></i>
            <p>Submit an extraction request to see results</p>
        `;
        
        resultsContainer.innerHTML = '';
        resultsContainer.appendChild(emptyState);
        resultsContainer.appendChild(jsonOutput);
    }

    /**
     * Show error message
     */
    function showError(message) {
        errorContainer.textContent = message;
        errorContainer.style.display = 'block';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            errorContainer.style.display = 'none';
        }, 5000);
    }

    /**
     * Toggle loading indicator
     */
    function toggleLoading(show) {
        loadingIndicator.style.display = show ? 'flex' : 'none';
    }
});
