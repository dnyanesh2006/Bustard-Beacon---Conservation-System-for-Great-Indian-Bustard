/* BUSTARD BEACON — Ranger Field Mode Geolocation & Camera JavaScript Engine */

function acquireCurrentGPSLocation() {
    const statusPill = document.getElementById("gps-status-indicator");
    const latInput = document.getElementById("field-latitude");
    const lngInput = document.getElementById("field-longitude");
    const accInput = document.getElementById("field-accuracy");
    const displayCoords = document.getElementById("gps-coords-display");
    const errDisplay = document.getElementById("gps-error-display");

    if (!navigator.geolocation) {
        if (errDisplay) {
            errDisplay.style.display = "block";
            errDisplay.innerText = "Geolocation is not supported by your current browser.";
        }
        return;
    }

    if (statusPill) {
        statusPill.className = "gps-status-pill gps-seeking";
        statusPill.innerHTML = '<i class="bi bi-arrow-repeat spin"></i> Acquiring Live GPS Signal...';
    }

    navigator.geolocation.getCurrentPosition(
        function(position) {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            const acc = position.coords.accuracy;

            if (latInput) latInput.value = lat;
            if (lngInput) lngInput.value = lng;
            if (accInput) accInput.value = acc;

            if (displayCoords) {
                displayCoords.innerHTML = `<strong>Lat:</strong> ${lat.toFixed(5)}, <strong>Lng:</strong> ${lng.toFixed(5)} <span class="badge bg-success ms-2">±${Math.round(acc)}m Accuracy</span>`;
            }

            if (statusPill) {
                statusPill.className = "gps-status-pill gps-acquired";
                statusPill.innerHTML = '<i class="bi bi-geo-alt-fill"></i> Live GPS Signal Acquired';
            }

            if (errDisplay) errDisplay.style.display = "none";
        },
        function(error) {
            let errorMsg = "Unable to retrieve device GPS coordinates.";
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    errorMsg = "A. Location permission denied. Please allow GPS access in your device/browser settings.";
                    break;
                case error.POSITION_UNAVAILABLE:
                    errorMsg = "B. Location information unavailable. Ensure device GPS hardware is enabled.";
                    break;
                case error.TIMEOUT:
                    errorMsg = "C. The request to get user location timed out.";
                    break;
                default:
                    errorMsg = "D. Browser/device does not support geolocation or an unknown error occurred.";
                    break;
            }

            if (statusPill) {
                statusPill.className = "gps-status-pill gps-denied";
                statusPill.innerHTML = '<i class="bi bi-exclamation-triangle-fill"></i> GPS Acquisition Failed';
            }

            if (errDisplay) {
                errDisplay.style.display = "block";
                errDisplay.innerHTML = `${errorMsg} <button type="button" class="btn btn-sm btn-outline-danger ms-2" onclick="acquireCurrentGPSLocation()">Retry GPS</button>`;
            }
        },
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        }
    );
}

function handleMultiplePhotoPreview(input) {
    const previewBox = document.getElementById("camera-preview-container");
    const retakeBtn = document.getElementById("camera-retake-btn");
    const dataInput = document.getElementById("captured_image_data");

    // Clear previous live capture if file is selected
    if (dataInput) dataInput.value = "";
    
    // Clear the container except for the retake button
    // Actually, in the template we changed it to a flex container. We need to clear previous img tags.
    Array.from(previewBox.children).forEach(child => {
        if (child.classList.contains('preview-item')) {
            previewBox.removeChild(child);
        }
    });

    if (input.files && input.files.length > 0) {
        previewBox.style.display = "flex";
        if (retakeBtn) retakeBtn.style.display = "inline-block";

        for (let i = 0; i < input.files.length; i++) {
            const file = input.files[i];
            
            // Basic MIME validation
            if (!file.type.match('image.*')) {
                alert("Please select valid image files only (JPEG, PNG, WEBP).");
                continue;
            }

            const reader = new FileReader();
            reader.onload = function(e) {
                const wrapper = document.createElement('div');
                wrapper.className = 'preview-item card bg-white border border-secondary shadow-sm';
                wrapper.style.width = '120px';
                
                const img = document.createElement('img');
                img.src = e.target.result;
                img.className = 'card-img';
                img.style.height = '120px';
                img.style.objectFit = 'contain';
                img.alt = 'Uploaded Image Preview ' + (i + 1);
                
                wrapper.appendChild(img);
                previewBox.appendChild(wrapper);
            };
            reader.readAsDataURL(file);
        }
    } else {
        previewBox.style.display = "none";
        if (retakeBtn) retakeBtn.style.display = "none";
    }
}

let watchId = null;

function startLiveLocationTracking() {
    const statusPill = document.getElementById("gps-status-indicator");
    if (!navigator.geolocation) return;

    watchId = navigator.geolocation.watchPosition(
        function(position) {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            
            // Post to backend
            fetch('/api/update-location/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ latitude: lat, longitude: lng })
            }).then(response => {
                if (response.ok && statusPill) {
                    statusPill.className = "gps-status-pill gps-acquired";
                    statusPill.innerHTML = '<i class="bi bi-geo-alt-fill"></i> Live GPS Tracking Active';
                }
            }).catch(e => console.error("Location update failed", e));
        },
        function(error) {
            if (statusPill) {
                statusPill.className = "gps-status-pill gps-denied";
                statusPill.innerHTML = '<i class="bi bi-exclamation-triangle-fill"></i> Live Tracking Failed';
            }
        },
        { enableHighAccuracy: true, maximumAge: 10000, timeout: 5000 }
    );
}

document.addEventListener("DOMContentLoaded", function() {
    // Auto-acquire GPS on field report pages if button present
    const autoGpsBtn = document.getElementById("btn-acquire-gps");
    if (autoGpsBtn) {
        acquireCurrentGPSLocation();
        autoGpsBtn.addEventListener("click", acquireCurrentGPSLocation);
    }

    // Start background tracking if on main field mode dashboard
    if (document.querySelector('.btn-field-sighting')) {
        startLiveLocationTracking();
    }
});

/* --- REAL CAMERA CAPTURE LOGIC --- */
let videoStream = null;

function startLiveCamera() {
    const video = document.getElementById("live-camera-video");
    const container = document.getElementById("live-camera-container");
    const errMsg = document.getElementById("camera-error-msg");
    const btnStart = document.getElementById("btn-start-camera");
    
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        errMsg.innerHTML = "Camera API not supported. This may happen if the site is not served over <b>HTTPS</b> or <b>localhost</b>.";
        errMsg.style.display = "block";
        return;
    }

    errMsg.style.display = "none";
    container.style.display = "block";
    btnStart.disabled = true;

    navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } } })
        .then(function(stream) {
            videoStream = stream;
            video.srcObject = stream;
            video.play();
        })
        .catch(function(err) {
            console.error("Camera access denied or unavailable:", err);
            if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                errMsg.innerText = "Camera permission denied. Please allow access in browser settings.";
            } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
                errMsg.innerText = "No camera hardware detected on this device.";
            } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
                errMsg.innerText = "Camera is already in use by another application.";
            } else {
                errMsg.innerText = "Camera unavailable: " + err.message;
            }
            errMsg.style.display = "block";
            container.style.display = "none";
            btnStart.disabled = false;
        });
}

function stopLiveCamera() {
    const container = document.getElementById("live-camera-container");
    const btnStart = document.getElementById("btn-start-camera");
    
    if (videoStream) {
        const tracks = videoStream.getTracks();
        tracks.forEach(track => track.stop());
        videoStream = null;
    }
    
    container.style.display = "none";
    btnStart.disabled = false;
}

function captureCameraFrame() {
    const video = document.getElementById("live-camera-video");
    const canvas = document.getElementById("camera-canvas");
    const dataInput = document.getElementById("captured_image_data");
    const previewBox = document.getElementById("camera-preview-container");
    const retakeBtn = document.getElementById("camera-retake-btn");
    const uploadInput = document.getElementById("photo_upload_input");
    
    if (video.readyState === video.HAVE_ENOUGH_DATA) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
        dataInput.value = dataUrl;
        if (uploadInput) uploadInput.value = ""; // Clear file uploads if live camera is used
        
        // Clear old previews
        Array.from(previewBox.children).forEach(child => {
            if (child.classList.contains('preview-item')) {
                previewBox.removeChild(child);
            }
        });
        
        const wrapper = document.createElement('div');
        wrapper.className = 'preview-item card bg-white border border-secondary shadow-sm';
        wrapper.style.width = '120px';
        
        const img = document.createElement('img');
        img.src = dataUrl;
        img.className = 'card-img';
        img.style.height = '120px';
        img.style.objectFit = 'contain';
        img.alt = 'Captured Field Photo Preview';
        
        wrapper.appendChild(img);
        previewBox.appendChild(wrapper);
        
        previewBox.style.display = "flex";
        if (retakeBtn) retakeBtn.style.display = "inline-block";
        
        stopLiveCamera();
    }
}

function clearPhotoPreview() {
    const previewBox = document.getElementById("camera-preview-container");
    const retakeBtn = document.getElementById("camera-retake-btn");
    const dataInput = document.getElementById("captured_image_data");
    const uploadInput = document.getElementById("photo_upload_input");
    
    Array.from(previewBox.children).forEach(child => {
        if (child.classList.contains('preview-item')) {
            previewBox.removeChild(child);
        }
    });
    previewBox.style.display = "none";
    if (retakeBtn) retakeBtn.style.display = "none";
    
    if (dataInput) dataInput.value = "";
    if (uploadInput) uploadInput.value = "";
}

// Stop camera if user leaves page
window.addEventListener("beforeunload", function() {
    stopLiveCamera();
});
