document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const pdfFileInput = document.getElementById('pdfFile');
    const extractionSchemaInput = document.getElementById('extractionSchema');
    const resultsContainer = document.getElementById('results');
    const resetButton = document.getElementById('resetButton');
    const loadingSpinner = document.getElementById('loadingSpinner');
    
    // Initialize tooltips
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(tooltip => {
        new bootstrap.Tooltip(tooltip);
    });
    
    // Handle form submission
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Validate file selection
        if (!pdfFileInput.files[0]) {
            showAlert('warning', 'Please select a PDF file to upload.');
            return;
        }
        
        // Create FormData object
        const formData = new FormData();
        formData.append('file', pdfFileInput.files[0]);
        
        // Add extraction schema if provided
        if (extractionSchemaInput.value) {
            formData.append('extraction_schema', extractionSchemaInput.value);
        }
        
        // Start loading state
        startLoading();
        
        // Send request to API
        fetch('/api/extract', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            // Stop loading state
            stopLoading();
            
            // Display the results
            if (data.success) {
                displayResults(data.data);
                showAlert('success', 'Data extracted successfully!');
            } else {
                displayResults({ error: data.error });
                showAlert('danger', 'Error: ' + data.error);
            }
            
            // Enable reset button
            resetButton.disabled = false;
        })
        .catch(error => {
            // Stop loading state
            stopLoading();
            
            // Display error
            displayResults({ error: 'Failed to connect to the server. Please try again.' });
            showAlert('danger', 'Error: Failed to connect to the server.');
            console.error('Error:', error);
            
            // Enable reset button
            resetButton.disabled = false;
        });
    });
    
    // Handle reset button click
    resetButton.addEventListener('click', function() {
        resetResults();
        uploadForm.reset();
        resetButton.disabled = true;
    });
    
    /**
     * Display extraction results in the results container
     */
    function displayResults(data) {
        // Clear previous results
        resultsContainer.innerHTML = '';
        
        if (data.error) {
            // Display error message
            resultsContainer.innerHTML = `
                <div class="alert alert-danger mb-0">
                    <h5 class="alert-heading">Extraction Failed</h5>
                    <p class="mb-0">${data.error}</p>
                </div>
            `;
            return;
        }
        
        // Create results display
        const resultHtml = `
            <div class="json-result">
                <pre><code>${syntaxHighlight(JSON.stringify(data, null, 2))}</code></pre>
            </div>
        `;
        
        resultsContainer.innerHTML = resultHtml;
    }
    
    /**
     * Reset the results container to its initial state
     */
    function resetResults() {
        resultsContainer.innerHTML = `
            <div class="text-center text-secondary p-5">
                <div class="mb-3">
                    <i class="bi bi-file-earmark-text" style="font-size: 3rem;"></i>
                </div>
                <p>Upload a PDF file to see the extracted data here.</p>
            </div>
        `;
    }
    
    /**
     * Set UI to loading state
     */
    function startLoading() {
        loadingSpinner.classList.remove('d-none');
        uploadForm.querySelectorAll('button, input, textarea').forEach(el => {
            el.disabled = true;
        });
    }
    
    /**
     * Reset UI from loading state
     */
    function stopLoading() {
        loadingSpinner.classList.add('d-none');
        uploadForm.querySelectorAll('button, input, textarea').forEach(el => {
            el.disabled = false;
        });
    }
    
    /**
     * Show an alert message that fades after a few seconds
     */
    function showAlert(type, message) {
        const alertContainer = document.querySelector('.alert-container');
        const alertId = 'alert-' + Date.now();
        
        const alertHtml = `
            <div id="${alertId}" class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        
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
        json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function(match) {
            let cls = 'text-info'; // number
            if (/^"/.test(match)) {
                if (/:$/.test(match)) {
                    cls = 'text-warning'; // key
                } else {
                    cls = 'text-success'; // string
                }
            } else if (/true|false/.test(match)) {
                cls = 'text-primary'; // boolean
            } else if (/null/.test(match)) {
                cls = 'text-danger'; // null
            }
            return '<span class="' + cls + '">' + match + '</span>';
        });
    }
});