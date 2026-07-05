document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('file-input');
    const dropZone = document.getElementById('drop-zone');
    const uploadSection = document.getElementById('upload-section');
    const loadingSection = document.getElementById('loading-section');
    const resultsSection = document.getElementById('results-section');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const gallery = document.getElementById('gallery');
    const statCount = document.getElementById('stat-count');
    const downloadAllBtn = document.getElementById('download-all-btn');

    // Lightbox Elements
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    const closeBtn = document.querySelector('.close-btn');
    const lbFilename = document.getElementById('lb-filename');
    const lbDims = document.getElementById('lb-dims');
    const lbSize = document.getElementById('lb-size');
    const lbFormat = document.getElementById('lb-format');
    const lbPage = document.getElementById('lb-page');
    const lbDownload = document.getElementById('lb-download');

    let currentJobId = null;

    // --- Helpers ---
    
    function formatBytes(bytes, decimals = 2) {
        if (!bytes || bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    // --- Upload Logic ---
    
    async function handleUpload(file) {
        if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
            alert('Please select a valid PDF file.');
            return;
        }

        const ocrToggle = document.getElementById('ocr-toggle');
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('apply_ocr', ocrToggle.checked);

        uploadSection.classList.add('hidden');
        loadingSection.classList.remove('hidden');
        progressFill.style.width = '0%';
        progressText.textContent = '0%';

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            currentJobId = data.job_id;
            pollProgress(currentJobId);
        } catch (error) {
            alert('Upload failed: ' + error);
            uploadSection.classList.remove('hidden');
            loadingSection.classList.add('hidden');
        }
    }

    // Click to upload
    dropZone.addEventListener('click', () => fileInput.click());

    // Auto-submit on file choice
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleUpload(fileInput.files[0]);
        }
    });

    // Drag & Drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-active');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-active');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-active');
        if (e.dataTransfer.files.length > 0) {
            handleUpload(e.dataTransfer.files[0]);
        }
    });

    // --- Polling & Results ---

    function pollProgress(jobId) {
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/api/progress/${jobId}`);
                const data = await response.json();

                if (data.status === 'completed') {
                    clearInterval(interval);
                    fetchResults(jobId);
                } else if (data.status === 'error') {
                    clearInterval(interval);
                    alert('Error: ' + data.error);
                    uploadSection.classList.remove('hidden');
                    loadingSection.classList.add('hidden');
                } else if (data.status === 'unknown') {
                    clearInterval(interval);
                    alert('Session lost due to server update. Please re-upload.');
                    uploadSection.classList.remove('hidden');
                    loadingSection.classList.add('hidden');
                } else {
                    progressFill.style.width = `${data.percentage}%`;
                    progressText.textContent = `${data.percentage}%`;
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
        }, 1000);
    }

    async function fetchResults(jobId) {
        try {
            const response = await fetch(`/api/results/${jobId}`);
            const data = await response.json();
            renderGallery(data.pages, jobId);
            
            loadingSection.classList.add('hidden');
            resultsSection.classList.remove('hidden');
            
            let totalTiles = 0;
            data.pages.forEach(p => totalTiles += p.images.length);
            statCount.textContent = totalTiles;
            
            downloadAllBtn.href = `/api/download/${jobId}`;
            downloadAllBtn.style.display = 'inline-flex';
        } catch (error) {
            alert('Failed to fetch results: ' + error);
        }
    }

    function renderGallery(pages, jobId) {
        gallery.innerHTML = '';
        
        pages.forEach(pageData => {
            const group = document.createElement('div');
            group.className = 'page-group';
            group.innerHTML = `<div class="page-number">Page ${pageData.page}</div>`;
            
            const grid = document.createElement('div');
            grid.className = 'masonry-grid';
            
            pageData.images.forEach(img => {
                const item = document.createElement('div');
                item.className = 'tile-card';
                
                const imgSrc = `/api/images/${jobId}/${img.filename}`;
                
                let badgeHtml = '';
                if (img.method === 'OCR') {
                    badgeHtml = `<span class="ocr-badge"><i class="fa-solid fa-camera"></i> OCR</span>`;
                }
                
                item.innerHTML = `
                    ${badgeHtml}
                    <img src="${imgSrc}" alt="Tile" loading="lazy">
                    <div class="tile-overlay">
                        <p>Tile Image</p>
                        <p class="dim">${img.width} x ${img.height} px</p>
                    </div>
                `;
                
                item.addEventListener('click', () => {
                    openLightbox(img, jobId);
                });
                
                grid.appendChild(item);
            });
            
            group.appendChild(grid);
            gallery.appendChild(group);
        });
    }

    function openLightbox(img, jobId) {
        lightboxImg.src = `/api/images/${jobId}/${img.filename}`;
        lbFilename.textContent = img.filename;
        lbDims.textContent = `${img.width} x ${img.height} px`;
        lbSize.textContent = formatBytes(parseInt(img.size));
        lbFormat.textContent = img.format || 'N/A';
        lbPage.textContent = img.page;
        lbDownload.href = `/api/images/${jobId}/${img.filename}`;
        lbDownload.setAttribute('download', img.filename);
        
        lightbox.classList.add('active');
    }

    closeBtn.addEventListener('click', () => lightbox.classList.remove('active'));
    lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) lightbox.classList.remove('active');
    });
});
