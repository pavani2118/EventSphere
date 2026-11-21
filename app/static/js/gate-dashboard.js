const token = sessionStorage.getItem("access_token") || localStorage.getItem("access_token");
const user = JSON.parse(sessionStorage.getItem("user") || localStorage.getItem("user") || "null");

function gateLogout() {
    sessionStorage.clear();
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    window.location.href = "/ui/login";
}

document.getElementById("gateLogout")?.addEventListener("click", gateLogout);

function gateHeaders() {
    return { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" };
}

async function gateRequest(url) {
    const response = await fetch(url, { headers: gateHeaders() });
    if (response.status === 401) gateLogout();
    if (response.status === 403) throw new Error("Gate Staff access is required.");
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Unable to load Gate Staff data.");
    return data;
}

function escapeGateText(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[character]);
}

function formatGateDate(value) {
    return value ? new Date(value).toLocaleString("en-US", {
        dateStyle: "medium", timeStyle: "short"
    }) : "Not available";
}

async function loadGateDashboard(eventId = "") {
    const error = document.getElementById("gateError");
    error.classList.add("d-none");

    try {
        const query = eventId ? `?event_id=${encodeURIComponent(eventId)}` : "";
        const data = await gateRequest(`/gate/dashboard${query}`);

        document.getElementById("ticketsExpected").textContent =
            data.total_tickets_expected_today;
        document.getElementById("ticketsCheckedIn").textContent =
            data.total_checked_in_today;
        document.getElementById("ticketsRemaining").textContent =
            data.remaining_tickets;

        const eventSelect = document.getElementById("eventSelect");
        if (eventSelect.options.length === 1) {
            data.events.forEach(event => {
                const option = document.createElement("option");
                option.value = event.event_id;
                option.textContent = event.title;
                eventSelect.appendChild(option);
            });
        }

        const selected = data.selected_event;
        const selectedEvent = document.getElementById("selectedEvent");
        if (!selected) {
            selectedEvent.innerHTML =
                '<p class="text-muted mb-0">No published events are available for gate operations.</p>';
        } else {
            selectedEvent.innerHTML = `
                <h3 class="h5 mb-2">${escapeGateText(selected.title)}</h3>
                <p class="mb-2"><i class="bi bi-geo-alt text-primary me-1"></i>${escapeGateText(selected.venue_name)} — ${escapeGateText(selected.venue_location)}</p>
                <p class="mb-3"><i class="bi bi-calendar3 text-primary me-1"></i>${escapeGateText(formatGateDate(selected.start_time))}</p>
                <div class="gate-event-metrics">
                    <span><strong>${selected.total_issued}</strong><small>Total issued</small></span>
                    <span><strong>${selected.checked_in}</strong><small>Checked in</small></span>
                    <span><strong>${selected.remaining}</strong><small>Remaining</small></span>
                </div>`;
        }

        const recent = document.getElementById("recentCheckIns");
        if (!data.recent_check_ins?.length) {
            recent.innerHTML =
                '<p class="text-muted mb-0">No recent check-in activity.</p>';
            return;
        }
        recent.innerHTML = data.recent_check_ins.map(record => `
            <div class="gate-recent-item">
                <span class="gate-recent-icon"><i class="bi bi-check-lg"></i></span>
                <div>
                    <strong>${escapeGateText(record.attendee_name)}</strong>
                    <small>Ticket #${record.ticket_id} · ${escapeGateText(record.event_title)}</small>
                    <time>${escapeGateText(formatGateDate(record.checked_in_at))}</time>
                </div>
            </div>`).join("");
    } catch (err) {
        error.textContent = err.message;
        error.classList.remove("d-none");
    }
}

if (!token) {
    window.location.href = "/ui/login";
} else {
    if (user?.full_name) {
        document.getElementById("gateWelcome").textContent =
            `Welcome, ${user.full_name}`;
    }
    document.getElementById("eventSelect").addEventListener("change", event => {
        loadGateDashboard(event.target.value);
    });
    loadGateDashboard();
}
