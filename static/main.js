/**
 * Document Data Extractor
 * Frontend JavaScript for handling document uploads and displaying results
 */

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('document-file');
    const extractBtn = document.getElementById('extract-btn');
    const loadingSpinner = document.getElementById('loading-spinner');
    const loadingOverlay = document.getElementById('loading-overlay');
    const resultsContainer = document.getElementById('results-container');
    const copyJsonBtn = document.getElementById('copy-json-btn');
    const schemaInput = document.getElementById('extraction-schema');
    
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
});