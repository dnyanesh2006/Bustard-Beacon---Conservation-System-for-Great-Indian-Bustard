/* BUSTARD BEACON — Interactive Conservation GIS Map Engine (Google Maps API) */

let bbMap = null;
let bbPolygons = [];
let bbIncidentMarkers = [];
let bbRangerMarkers = [];
let bbZoneBoundsMap = {};
let bbInfoWindow = null;

function initSanctuaryMap() {
    const mapElement = document.getElementById("conservation-map");
    if (!mapElement) return;

    // Check if Google Maps is loaded
    if (typeof google === "undefined" || !google.maps) {
        console.warn("Google Maps JavaScript API not yet loaded, retrying...");
        const fallbackAlert = document.getElementById('map-fallback-alert');
        if (fallbackAlert) fallbackAlert.style.display = 'block';
        return;
    }

    try {
        // Center on Nannaj Sanctuary / Solapur, Maharashtra (~17.828° N, 75.857° E)
        const sanctuaryCenter = { lat: 17.828, lng: 75.857 };

        bbMap = new google.maps.Map(mapElement, {
            center: sanctuaryCenter,
            zoom: 12,
            mapTypeId: google.maps.MapTypeId.ROADMAP,
            mapTypeControl: true,
            mapTypeControlOptions: {
                style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
                position: google.maps.ControlPosition.TOP_LEFT
            },
            zoomControl: true,
            zoomControlOptions: {
                position: google.maps.ControlPosition.RIGHT_BOTTOM
            },
            scaleControl: true,
            streetViewControl: false,
            fullscreenControl: true,
            fullscreenControlOptions: {
                position: google.maps.ControlPosition.RIGHT_TOP
            }
        });

        bbInfoWindow = new google.maps.InfoWindow();

        // Close InfoWindow when map is clicked
        bbMap.addListener("click", () => {
            if (bbInfoWindow) bbInfoWindow.close();
        });

        // Create Custom Layer Toggle Control (Top Right)
        setupLayerToggleControl();

        // Load Real Conservation Data from Backend REST API
        loadSanctuaryData();

    } catch (err) {
        console.error("Error initializing Google Maps Sanctuary GIS:", err);
        const fallbackAlert = document.getElementById('map-fallback-alert');
        if (fallbackAlert) fallbackAlert.style.display = 'block';
    }
}

function setupLayerToggleControl() {
    const controlDiv = document.createElement("div");
    controlDiv.style.margin = "10px";
    controlDiv.style.backgroundColor = "#ffffff";
    controlDiv.style.border = "1px solid #d1d5db";
    controlDiv.style.borderRadius = "8px";
    controlDiv.style.boxShadow = "0 2px 6px rgba(0,0,0,0.15)";
    controlDiv.style.padding = "8px 12px";
    controlDiv.style.fontFamily = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    controlDiv.style.fontSize = "12px";
    controlDiv.style.color = "#111815";
    controlDiv.style.zIndex = "5";

    controlDiv.innerHTML = `
        <div style="font-weight: 700; margin-bottom: 6px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #4b5563;">
            GIS Map Layers
        </div>
        <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px; cursor: pointer;">
            <input type="checkbox" id="toggle-zones" checked style="accent-color: #2e7d32;">
            <span style="font-weight: 600;">Sanctuary Zones</span>
        </label>
        <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px; cursor: pointer;">
            <input type="checkbox" id="toggle-incidents" checked style="accent-color: #d97706;">
            <span style="font-weight: 600;">Field Incidents</span>
        </label>
        <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
            <input type="checkbox" id="toggle-rangers" checked style="accent-color: #7c3aed;">
            <span style="font-weight: 600;">Active Rangers</span>
        </label>
    `;

    bbMap.controls[google.maps.ControlPosition.TOP_RIGHT].push(controlDiv);

    // Add Toggle Event Listeners
    setTimeout(() => {
        const toggleZones = document.getElementById("toggle-zones");
        const toggleIncidents = document.getElementById("toggle-incidents");
        const toggleRangers = document.getElementById("toggle-rangers");

        if (toggleZones) {
            toggleZones.addEventListener("change", (e) => {
                const visible = e.target.checked;
                bbPolygons.forEach(p => p.setMap(visible ? bbMap : null));
            });
        }
        if (toggleIncidents) {
            toggleIncidents.addEventListener("change", (e) => {
                const visible = e.target.checked;
                bbIncidentMarkers.forEach(m => m.setMap(visible ? bbMap : null));
            });
        }
        if (toggleRangers) {
            toggleRangers.addEventListener("change", (e) => {
                const visible = e.target.checked;
                bbRangerMarkers.forEach(m => m.setMap(visible ? bbMap : null));
            });
        }
    }, 100);
}

function loadSanctuaryData() {
    fetch("/api/map-data/")
        .then(response => {
            if (!response.ok) throw new Error("HTTP error " + response.status);
            return response.json();
        })
        .then(data => {
            // 1. Render Conservation Zone Polygons
            if (data.zones && data.zones.length > 0) {
                data.zones.forEach(zone => {
                    if (zone.coordinates && zone.coordinates.length > 0) {
                        const paths = zone.coordinates.map(pt => ({ lat: pt[0], lng: pt[1] }));
                        const bounds = new google.maps.LatLngBounds();
                        paths.forEach(pt => bounds.extend(pt));
                        bbZoneBoundsMap[zone.id] = bounds;

                        const zoneColor = zone.color || "#2e7d32";
                        const polygon = new google.maps.Polygon({
                            paths: paths,
                            strokeColor: zoneColor,
                            strokeOpacity: 0.9,
                            strokeWeight: 2.5,
                            fillColor: zoneColor,
                            fillOpacity: 0.22,
                            map: bbMap
                        });

                        const popupHtml = `
                            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; min-width: 210px; padding: 4px;">
                                <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                                    <span style="display:inline-block; width:12px; height:12px; border-radius:3px; background-color:${zoneColor};"></span>
                                    <strong style="color: #111815; font-size: 14px;">${zone.name}</strong>
                                </div>
                                <div style="font-size: 12px; color: #4b5563; margin-bottom: 6px;">
                                    <b>Code:</b> ${zone.code} &bull; <b>Type:</b> ${zone.type}
                                </div>
                                <span style="font-size: 11px; background: #e0f2fe; color: #0369a1; padding: 2px 6px; border-radius: 4px; font-weight: 600;">
                                    Official Sanctuary Zone
                                </span>
                            </div>
                        `;

                        polygon.addListener("click", (e) => {
                            bbInfoWindow.setContent(popupHtml);
                            bbInfoWindow.setPosition(e.latLng);
                            bbInfoWindow.open(bbMap);
                        });

                        bbPolygons.push(polygon);
                    }
                });
            }

            // 2. Render Field Incident Markers
            if (data.incidents && data.incidents.length > 0) {
                data.incidents.forEach(inc => {
                    let color = "#f59e0b"; // High (amber)
                    let strokeColor = "#b45309";
                    if (inc.priority === "CRITICAL") {
                        color = "#ef4444";
                        strokeColor = "#b91c1c";
                    } else if (inc.priority === "LOW") {
                        color = "#10b981";
                        strokeColor = "#047857";
                    } else if (inc.priority === "MEDIUM") {
                        color = "#3b82f6";
                        strokeColor = "#1d4ed8";
                    }

                    const marker = new google.maps.Marker({
                        position: { lat: inc.latitude, lng: inc.longitude },
                        map: bbMap,
                        title: `${inc.incident_id} (${inc.priority})`,
                        icon: {
                            path: google.maps.SymbolPath.CIRCLE,
                            fillColor: color,
                            fillOpacity: 0.9,
                            strokeColor: strokeColor,
                            strokeWeight: 2,
                            scale: 8
                        }
                    });

                    let imgHtml = inc.image_url ? `<img src="${inc.image_url}" alt="Incident image" style="width:100%; max-height:130px; object-fit:cover; border-radius:6px; margin: 6px 0;">` : '';

                    const popupHtml = `
                        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 260px; padding: 4px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                                <strong style="color: #111815; font-size: 13px;">${inc.incident_id}</strong>
                                <span style="font-size: 10px; font-weight: 700; background: ${color}; color: #ffffff; padding: 2px 6px; border-radius: 10px;">
                                    ${inc.priority}
                                </span>
                            </div>
                            <div style="font-weight: 600; font-size: 13px; color: #1f2937; margin-bottom: 4px;">${inc.category}</div>
                            <div style="font-size: 12px; color: #4b5563; margin-bottom: 6px; line-height: 1.4;">${inc.description}</div>
                            ${imgHtml}
                            <hr style="margin: 6px 0; border: 0; border-top: 1px solid #e5e7eb;">
                            <div style="font-size: 11px; color: #6b7280; line-height: 1.45;">
                                <div><b>Reporter:</b> ${inc.reporter}</div>
                                <div><b>Reported:</b> ${inc.reported_at}</div>
                                <div><b>Zone:</b> ${inc.zone_name}</div>
                                ${inc.weather_temp ? `<div><b>Weather:</b> ${inc.weather_temp}°C, ${inc.weather_cond || ''}</div>` : ''}
                            </div>
                        </div>
                    `;

                    marker.addListener("click", () => {
                        bbInfoWindow.setContent(popupHtml);
                        bbInfoWindow.open(bbMap, marker);
                    });

                    bbIncidentMarkers.push(marker);
                });
            }

            // 3. Render Active Field Rangers
            if (data.rangers && data.rangers.length > 0) {
                data.rangers.forEach(rng => {
                    const marker = new google.maps.Marker({
                        position: { lat: rng.latitude, lng: rng.longitude },
                        map: bbMap,
                        title: `Ranger: ${rng.name}`,
                        icon: {
                            path: google.maps.SymbolPath.CIRCLE,
                            fillColor: "#7c3aed",
                            fillOpacity: 1,
                            strokeColor: "#ffffff",
                            strokeWeight: 2.5,
                            scale: 9
                        }
                    });

                    const popupHtml = `
                        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 4px;">
                            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                                <span style="font-size: 14px;">👮</span>
                                <strong style="color: #7c3aed; font-size: 13px;">Active Field Ranger</strong>
                            </div>
                            <div style="font-size: 12px; color: #111815;"><b>Name:</b> ${rng.name}</div>
                            <div style="font-size: 11px; color: #6b7280; margin-top: 2px;"><b>Badge:</b> ${rng.badge || 'N/A'} &bull; <b>Updated:</b> ${rng.updated_at}</div>
                        </div>
                    `;

                    marker.addListener("click", () => {
                        bbInfoWindow.setContent(popupHtml);
                        bbInfoWindow.open(bbMap, marker);
                    });

                    bbRangerMarkers.push(marker);
                });
            }
        })
        .catch(err => {
            console.warn("Error loading GIS map data:", err);
            const fallbackAlert = document.getElementById('map-fallback-alert');
            if (fallbackAlert) fallbackAlert.style.display = 'block';
        });
}

function zoomToZone(zoneId) {
    if (bbMap && bbZoneBoundsMap[zoneId]) {
        bbMap.fitBounds(bbZoneBoundsMap[zoneId]);
    } else if (bbMap) {
        bbMap.setCenter({ lat: 17.828, lng: 75.857 });
        bbMap.setZoom(13);
    }
}

function resetSanctuaryMapView() {
    if (bbMap) {
        bbMap.setCenter({ lat: 17.828, lng: 75.857 });
        bbMap.setZoom(12);
    }
}

// Global exposure for UI buttons
window.zoomToZone = zoomToZone;
window.resetSanctuaryMapView = resetSanctuaryMapView;

document.addEventListener("DOMContentLoaded", function() {
    if (typeof google !== "undefined" && google.maps) {
        initSanctuaryMap();
    } else {
        // Poll briefly if script is asynchronously completing
        let attempts = 0;
        const interval = setInterval(() => {
            attempts++;
            if (typeof google !== "undefined" && google.maps) {
                clearInterval(interval);
                initSanctuaryMap();
            } else if (attempts > 30) {
                clearInterval(interval);
                console.warn("Timed out waiting for Google Maps API.");
                const fallbackAlert = document.getElementById('map-fallback-alert');
                if (fallbackAlert) fallbackAlert.style.display = 'block';
            }
        }, 100);
    }
});
