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
        const timerText = document.getElementById('timer-text');
        
        let timerInterval = null;
        let secondsLeft = 0;
        let timerStarted = false;

        const interval = setInterval(async () => {
            try {
                const res = await fetch(`/api/progress/${jobId}`);
                const data = await res.json();
                
                if (data.status === 'error') {
                    clearInterval(interval);
                    if(timerInterval) clearInterval(timerInterval);
                    alert('Error during extraction: ' + data.error);
                    loadingSection.classList.add('hidden');
                    uploadSection.classList.remove('hidden');
                    return;
                }
                
                if (data.percentage !== undefined) {
                    progressFill.style.width = `${data.percentage}%`;
                    progressText.textContent = `${data.percentage}%`;
                }

                // Start timer once we know the total pages
                if (data.total && !timerStarted) {
                    timerStarted = true;
                    // Check if OCR is actually working on the server
                    if (data.ocr_enabled === false) {
                        console.warn("OCR engine is not detected on the server.");
                        document.getElementById('loading-status').textContent = "OCR Engine Offline - Names/Sizes will be missing";
                    }

                    // Estimate: 5s per page on average * 1.5 safety factor
                    secondsLeft = Math.ceil(data.total * 5 * 1.5);
                    
                    timerInterval = setInterval(() => {
                        if (secondsLeft > 0) {
                            secondsLeft--;
                            const mins = Math.floor(secondsLeft / 60);
                            const secs = secondsLeft % 60;
                            timerText.textContent = `${mins}m ${secs}s`;
                        }
                    }, 1000);
                }
                
                if (data.status === 'completed') {
                    clearInterval(interval);
                    if(timerInterval) clearInterval(timerInterval);
                    timerText.textContent = "Finalizing...";
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
        const MAX_ATTEMPTS = 30;
        try {
            const res = await fetch(`/api/results/${jobId}`);
            if (!res.ok) throw new Error(`Server error: ${res.status}`);
            const data = await res.json();

            if (!data.pages) throw new Error('No pages data in response.');

            renderGallery(data.pages, jobId);

            loadingSection.classList.add('hidden');
            resultsSection.classList.remove('hidden');
        } catch (error) {
            console.error(`Fetch attempt ${attempt + 1} failed:`, error);
            if (attempt < MAX_ATTEMPTS) {
                // Exponential backoff or just wait longer
                const delay = attempt < 10 ? 1000 : 2000;
                setTimeout(() => fetchResults(jobId, attempt + 1), delay);
            } else {
                alert(`Error loading results: ${error.message}\nThis usually happens if the catalogue is very large. Try refreshing the page once the processing hit 100%.`);
                loadingSection.classList.add('hidden');
                uploadSection.classList.remove('hidden');
            }
        }
    }

    // Rendering — page-grouped layout with metadata cards
    function renderGallery(pages, jobId) {
        gallery.innerHTML = '';

        // Count total tiles
        const totalTiles = pages.reduce((sum, p) => sum + p.images.length, 0);
        statCount.textContent = totalTiles;

        const downloadAllBtn = document.getElementById('download-all-btn');

        if (totalTiles === 0) {
            gallery.innerHTML = '<p style="text-align:center;color:var(--text-muted)">No tiles found in this document.</p>';
            if (downloadAllBtn) downloadAllBtn.style.display = 'none';
            return;
        }

        if (downloadAllBtn) {
            downloadAllBtn.href = `/api/download/${jobId}`;
            downloadAllBtn.style.display = 'inline-flex';
        }

        let imgIndex = 0;

        pages.forEach(pageData => {
            const { page, metadata, images } = pageData;

            // Page group wrapper
            const group = document.createElement('div');
            group.className = 'page-group';

            // Page label
            const pageLabel = document.createElement('div');
            pageLabel.className = 'page-label';
            pageLabel.textContent = `Page ${page}`;
            group.appendChild(pageLabel);

            // Split Container for Images and Data
            const splitContainer = document.createElement('div');
            splitContainer.className = 'split-container';

            // --- Portion 1: Images Card ---
            const imagesCard = document.createElement('div');
            imagesCard.className = 'portion-card images-portion';
            imagesCard.innerHTML = `<div class="portion-title">Images</div>`;
            
            const grid = document.createElement('div');
            grid.className = 'masonry-grid';

            images.forEach(imgData => {
                const imgUrl = `/api/images/${jobId}/${imgData.filename}`;
                const card = document.createElement('div');
                card.className = 'tile-card';
                card.style.animationDelay = `${imgIndex * 0.04}s`;
                imgIndex++;

                const img = document.createElement('img');
                img.src = imgUrl;
                img.alt = imgData.filename;
                img.onload = () => {
                    const rowHeight = 20, gap = 20;
                    const height = img.naturalHeight * (card.clientWidth / img.naturalWidth);
                    const rowSpan = Math.ceil((height + gap) / (rowHeight + gap)) + 3;
                    card.style.gridRowEnd = `span ${rowSpan}`;
                };

                const overlay = document.createElement('div');
                overlay.className = 'tile-overlay';
                overlay.innerHTML = `<p>${imgData.name || 'Tile'}</p>`;

                card.appendChild(img);
                card.appendChild(overlay);
                card.addEventListener('click', () => openLightbox(imgUrl, imgData));
                grid.appendChild(card);
            });
            
            imagesCard.appendChild(grid);

            // --- Portion 2: Data Card ---
            const dataCard = document.createElement('div');
            dataCard.className = 'portion-card data-portion';
            dataCard.innerHTML = `<div class="portion-title">Specifications</div>`;

            const table = document.createElement('div');
            table.className = 'data-table';
            
            // Header
            table.innerHTML = `
                <div class="table-row table-header">
                    <div class="col-name">Name</div>
                    <div class="col-size">Size</div>
                    <div class="col-surface">Surface</div>
                </div>
            `;

            if (metadata && metadata.products) {
                metadata.products.forEach(prod => {
                    const row = document.createElement('div');
                    row.className = 'table-row';
                    row.innerHTML = `
                        <div class="col-name">${prod.name || '-'}</div>
                        <div class="col-size">${prod.size || '-'}</div>
                        <div class="col-surface">${prod.surface || '-'}</div>
                    `;
                    table.appendChild(row);
                });
            }

            dataCard.appendChild(table);

            // Add portions to split container
            splitContainer.appendChild(imagesCard);
            splitContainer.appendChild(dataCard);
            group.appendChild(splitContainer);
            
            gallery.appendChild(group);
        });
    }


    // Lightbox Logic
    function openLightbox(url, data) {
        lbImg.src = url;
        lbFilename.textContent = data.name || data.filename;
        lbDims.textContent = `${data.width_px} x ${data.height_px}`;
        lbPage.textContent = data.page;
        lbDownload.href = url;

        // Dynamic Info Grid for Lightbox
        const infoGrid = document.querySelector('.info-grid');
        
        const formatBytes = (bytes) => {
            if (!bytes) return '-';
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / 1048576).toFixed(1) + ' MB';
        };

        infoGrid.innerHTML = `
            <div class="info-item"><span class="label">Dimensions</span><span class="value">${data.width_px} x ${data.height_px} px</span></div>
            <div class="info-item"><span class="label">File Size</span><span class="value">${formatBytes(data.size_bytes)}</span></div>
        `;

        const fields = [
            { key: 'size',      label: 'Size' },
            { key: 'surface',   label: 'Surface' },
            { key: 'thickness', label: 'Thickness' },
            { key: 'faces',     label: 'Faces' }
        ];

        fields.forEach(({ key, label }) => {
            if (data[key]) {
                const item = document.createElement('div');
                item.className = 'info-item';
                item.innerHTML = `<span class="label">${label}</span><span class="value">${data[key]}</span>`;
                infoGrid.appendChild(item);
            }
        });

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
