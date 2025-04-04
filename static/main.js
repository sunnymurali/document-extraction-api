document.addEventListener('DOMContentLoaded', function() {
    const extractionForm = document.getElementById('extraction-form');
    const extractButton = document.getElementById('extract-button');
    const resultsContainer = document.getElementById('results-container');
    const jsonViewer = document.getElementById('json-viewer');
    const statusContainer = document.getElementById('status-container');
    const copyResultsButton = document.getElementById('copy-results');
    
    // Handle form submission
    extractionForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Validate form
        const fileInput = document.getElementById('pdfFile');
        if (!fileInput.files.length) {
            showAlert('error', 'Please select a PDF file to extract data from.');
            return;
        }
        
        const file = fileInput.files[0];
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            showAlert('error', 'Only PDF files are supported.');
            return;
        }
        
        // Start extraction
        startLoading();
        
        // Create form data
        const formData = new FormData();
        formData.append('file', file);
        
        const schemaInput = document.getElementById('extractionSchema');
        if (schemaInput.value.trim()) {
            formData.append('extraction_schema', schemaInput.value.trim());
        }
        
        try {
            // Send API request
            const response = await fetch('/api/extract', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                displayResults(data.data);
                showAlert('success', 'Data extracted successfully!');
            } else {
                const errorMessage = data.error || 'Failed to extract data from the PDF.';
                showAlert('error', errorMessage);
                resetResults();
            }
        } catch (error) {
            console.error('Error during extraction:', error);
            showAlert('error', 'An error occurred during data extraction. Please try again.');
            resetResults();
        } finally {
            stopLoading();
        }
    });
    
    // Handle copy results button
    copyResultsButton.addEventListener('click', function() {
        // Get the text from the json viewer
        const resultText = jsonViewer.textContent;
        
        // Copy to clipboard
        navigator.clipboard.writeText(resultText)
            .then(() => {
                // Temporarily change button text
                const originalText = copyResultsButton.innerHTML;
                copyResultsButton.innerHTML = '<i class="bi bi-check-lg"></i> Copied!';
                
                setTimeout(() => {
                    copyResultsButton.innerHTML = originalText;
                }, 2000);
            })
            .catch(err => {
                console.error('Failed to copy text: ', err);
                showAlert('error', 'Failed to copy results to clipboard');
            });
    });
    
    // Function to display the extraction results
    function displayResults(data) {
        // Hide the empty state
        resultsContainer.classList.add('d-none');
        
        // Show the JSON viewer
        jsonViewer.classList.remove('d-none');
        
        // Format and display the JSON data
        const formattedJson = JSON.stringify(data, null, 2);
        jsonViewer.innerHTML = syntaxHighlight(formattedJson);
        
        // Enable the copy button
        copyResultsButton.disabled = false;
    }
    
    // Function to reset the results
    function resetResults() {
        // Show the empty state
        resultsContainer.classList.remove('d-none');
        
        // Hide the JSON viewer
        jsonViewer.classList.add('d-none');
        
        // Disable the copy button
        copyResultsButton.disabled = true;
    }
    
    // Function to show loading state
    function startLoading() {
        // Disable the extract button and show loading spinner
        extractButton.disabled = true;
        extractButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Extracting...';
    }
    
    // Function to stop loading state
    function stopLoading() {
        // Enable the extract button and restore text
        extractButton.disabled = false;
        extractButton.innerHTML = '<i class="bi bi-magic"></i> Extract Data';
    }
    
    // Function to show alerts
    function showAlert(type, message) {
        // Clear any existing alerts
        statusContainer.innerHTML = '';
        
        // Create alert element
        const alertElement = document.createElement('div');
        alertElement.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
        alertElement.role = 'alert';
        
        // Add alert content
        alertElement.innerHTML = `
            <i class="bi bi-${type === 'error' ? 'exclamation-triangle' : 'check-circle'}"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        // Add alert to container
        statusContainer.appendChild(alertElement);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            alertElement.classList.remove('show');
            setTimeout(() => alertElement.remove(), 150);
        }, 5000);
    }
    
    // Function to syntax highlight JSON for display
    function syntaxHighlight(json) {
        if (!json) return '';
        
        // Replace characters to prevent XSS
        json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        
        // Add syntax highlighting
        return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function(match) {
            let cls = 'json-number';
            if (/^"/.test(match)) {
                if (/:$/.test(match)) {
                    cls = 'json-key';
                    // Remove the colon from the match
                    match = match.replace(/:$/, '') + ':';
                } else {
                    cls = 'json-string';
                }
            } else if (/true|false/.test(match)) {
                cls = 'json-boolean';
            } else if (/null/.test(match)) {
                cls = 'json-null';
            }
            
            // If it's a key (ends with a colon)
            if (cls === 'json-key') {
                return '<span class="' + cls + '">' + match.substring(0, match.length - 1) + '</span>:';
            }
            
            return '<span class="' + cls + '">' + match + '</span>';
        });
    }
});
