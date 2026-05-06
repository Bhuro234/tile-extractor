document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadSection = document.getElementById('upload-section');
    const loadingSection = document.getElementById('loading-section');
    const resultsSection = document.getElementById('results-section');
    const gallery = document.getElementById('gallery');
    const statCount = document.getElementById('stat-count');

    // Lightbox elements
    const lightbox = document.getElementById('lightbox');
    const lbClose = document.querySelector('.close-btn');
    const lbImg = document.getElementById('lightbox-img');
    const lbFilename = document.getElementById('lb-filename');
    const lbDims = document.getElementById('lb-dims');
    const lbSize = document.getElementById('lb-size');
    const lbFormat = document.getElementById('lb-format');
    const lbPage = document.getElementById('lb-page');
    const lbDownload = document.getElementById('lb-download');

    // Drag and Drop Logic
    dropZone.addEventListener('click', () => fileInput.click());

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
    });

    dropZone.addEventListener('drop', handleDrop, false);
    fileInput.addEventListener('change', function() {
        if (this.files.length) handleFiles(this.files);
    });

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    function handleFiles(files) {
        const file = files[0];
        if (file && file.type === 'application/pdf') {
            uploadPDF(file);
        } else {
            alert('Please upload a valid PDF catalogue.');
        }
    }

    // API Interaction
    async function uploadPDF(file) {
        const formData = new FormData();
        formData.append('file', file);

        // UI transitions
        uploadSection.classList.add('hidden');
        loadingSection.classList.remove('hidden');
        
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');
        const loadingStatus = document.getElementById('loading-status');
        
        progressFill.style.width = '0%';
        progressText.textContent = '0%';
        loadingStatus.textContent = 'Extracting Tiles...';

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) throw new Error('Upload or extraction failed.');
            
            const data = await response.json();
            pollProgress(data.job_id);
            
        } catch (error) {
            console.error(error);
            alert('Error processing file. Please try again.');
            loadingSection.classList.add('hidden');
            uploadSection.classList.remove('hidden');
        }
    }

    async function pollProgress(jobId) {
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');
        
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`/api/progress/${jobId}`);
                const data = await res.json();
                
                if (data.status === 'error') {
                    clearInterval(interval);
                    alert('Error during extraction: ' + data.error);
                    loadingSection.classList.add('hidden');
                    uploadSection.classList.remove('hidden');
                    return;
                }
                
                if (data.percentage !== undefined) {
                    progressFill.style.width = `${data.percentage}%`;
                    progressText.textContent = `${data.percentage}%`;
                }
                
                if (data.status === 'completed') {
                    clearInterval(interval);
                    progressFill.style.width = '100%';
                    progressText.textContent = '100%';
                    document.getElementById('loading-status').textContent = 'Loading Results...';
                    setTimeout(() => {
                        fetchResults(jobId);
                    }, 600);
                }
            } catch (err) {
                console.error("Polling error", err);
            }
        }, 500);
    }

    async function fetchResults(jobId, attempt = 0) {
        const MAX_ATTEMPTS = 10;
        try {
            const res = await fetch(`/api/results/${jobId}`);
            if (!res.ok) throw new Error(`Server error: ${res.status}`);
            const data = await res.json();

            if (!data.images) throw new Error('No images data in response.');
            
            renderGallery(data.images, jobId);
            
            loadingSection.classList.add('hidden');
            resultsSection.classList.remove('hidden');
        } catch (error) {
            console.error(`Fetch attempt ${attempt + 1} failed:`, error);
            if (attempt < MAX_ATTEMPTS) {
                // Retry after 1 second
                setTimeout(() => fetchResults(jobId, attempt + 1), 1000);
            } else {
                alert('Could not load results after several attempts. Please try refreshing the page.');
                loadingSection.classList.add('hidden');
                uploadSection.classList.remove('hidden');
            }
        }
    }

    // Rendering
    function renderGallery(images, jobId) {
        gallery.innerHTML = '';
        statCount.textContent = images.length;
        
        const downloadAllBtn = document.getElementById('download-all-btn');

        if (images.length === 0) {
            gallery.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--text-muted);">No tiles found in this document.</p>';
            if(downloadAllBtn) downloadAllBtn.style.display = 'none';
            return;
        }

        if(downloadAllBtn) {
            downloadAllBtn.href = `/api/download/${jobId}`;
            downloadAllBtn.style.display = 'inline-flex';
        }

        images.forEach((imgData, index) => {
            const imgUrl = `/api/images/${jobId}/${imgData.filename}`;
            
            const card = document.createElement('div');
            card.className = 'tile-card';
            card.style.animationDelay = `${index * 0.05}s`;
            
            const img = document.createElement('img');
            img.src = imgUrl;
            img.alt = imgData.filename;
            
            // Wait for image to load to set row span for masonry effect
            img.onload = () => {
                const rowHeight = 20;
                const gap = 20;
                const height = img.naturalHeight * (card.clientWidth / img.naturalWidth);
                const rowSpan = Math.ceil((height + gap) / (rowHeight + gap)) + 3; // +3 for overlay padding space
                card.style.gridRowEnd = `span ${rowSpan}`;
            };

            const overlay = document.createElement('div');
            overlay.className = 'tile-overlay';
            overlay.innerHTML = `
                <p>Page ${imgData.page}</p>
                <div class="dim">${imgData.width_px} &times; ${imgData.height_px} px</div>
            `;

            card.appendChild(img);
            card.appendChild(overlay);
            gallery.appendChild(card);

            // Lightbox interaction
            card.addEventListener('click', () => openLightbox(imgUrl, imgData));
        });
    }

    // Lightbox Logic
    function openLightbox(url, data) {
        lbImg.src = url;
        lbFilename.textContent = data.filename;
        lbDims.textContent = `${data.width_px} x ${data.height_px} px`;
        lbSize.textContent = `${data.size_kb} KB`;
        lbFormat.textContent = data.format;
        lbPage.textContent = `Page ${data.page}`;
        lbDownload.href = url;
        
        lightbox.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    function closeLightbox() {
        lightbox.classList.remove('active');
        document.body.style.overflow = '';
        setTimeout(() => { lbImg.src = ''; }, 400); // clear after transition
    }

    lbClose.addEventListener('click', closeLightbox);
    lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) closeLightbox();
    });
    
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && lightbox.classList.contains('active')) {
            closeLightbox();
        }
    });
});
