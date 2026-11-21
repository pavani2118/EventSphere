const token = sessionStorage.getItem("access_token") || localStorage.getItem("access_token");

function gateLogout() {
    sessionStorage.clear();
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    window.location.href = "/ui/login";
}

document.getElementById("gateLogout")?.addEventListener("click", gateLogout);
if (!token) window.location.href = "/ui/login";

function escapeEventText(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[character]);
}

async function loadGateEvents() {
    const grid = document.getElementById("gateEventsGrid");
    const error = document.getElementById("gateEventsError");
    try {
        const response = await fetch("/gate/events", {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (response.status === 401) gateLogout();
        if (response.status === 403) throw new Error("Gate Staff access is required.");
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Could not load events.");
        if (!data.events.length) {
            grid.innerHTML =
                '<div class="col-12 text-center text-muted py-5">No published events are available.</div>';
            return;
        }
        grid.innerHTML = data.events.map(event => `
            <div class="col-md-6 col-xl-4">
                <article class="card gate-event-card h-100">
                    <div class="card-body">
                        <span class="status-badge status-published">Published</span>
                        <h2 class="h5 mt-3">${escapeEventText(event.title)}</h2>
                        <p class="text-muted mb-2">${escapeEventText(event.category)}</p>
                        <p class="mb-1"><i class="bi bi-geo-alt text-primary me-1"></i>${escapeEventText(event.venue_name)}</p>
                        <p class="text-muted mb-3">${escapeEventText(event.venue_location)}</p>
                        <div class="gate-event-metrics">
                            <span><strong>${event.total_issued}</strong><small>Issued</small></span>
                            <span><strong>${event.checked_in}</strong><small>Checked in</small></span>
                            <span><strong>${event.remaining}</strong><small>Remaining</small></span>
                        </div>
                        <a class="btn btn-outline-primary w-100 mt-3" href="/ui/gate/scanner">Scan tickets</a>
                    </div>
                </article>
            </div>`).join("");
    } catch (err) {
        error.textContent = err.message;
        error.classList.remove("d-none");
    }
}

loadGateEvents();
