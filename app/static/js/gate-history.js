const token = sessionStorage.getItem("access_token") || localStorage.getItem("access_token");
let currentPage = 1;

function gateLogout() {
    sessionStorage.clear();
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    window.location.href = "/ui/login";
}

document.getElementById("gateLogout")?.addEventListener("click", gateLogout);
if (!token) window.location.href = "/ui/login";

function escapeHistory(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[character]);
}

function formatHistoryDate(value) {
    return value ? new Date(value).toLocaleString("en-US", {
        dateStyle: "medium", timeStyle: "short"
    }) : "Not available";
}

async function gateHistoryRequest(url) {
    const response = await fetch(url, {
        headers: { "Authorization": `Bearer ${token}` }
    });
    if (response.status === 401) gateLogout();
    if (response.status === 403) throw new Error("Gate Staff access is required.");
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Could not load check-in history.");
    return data;
}

async function loadEvents() {
    const select = document.getElementById("eventFilter");
    try {
        const data = await gateHistoryRequest("/gate/events");
        data.events.forEach(event => {
            const option = document.createElement("option");
            option.value = event.event_id;
            option.textContent = event.title;
            select.appendChild(option);
        });
    } catch (error) {
        document.getElementById("historyError").textContent = error.message;
        document.getElementById("historyError").classList.remove("d-none");
    }
}

async function loadHistory(page = 1) {
    currentPage = page;
    const table = document.getElementById("historyTable");
    const error = document.getElementById("historyError");
    error.classList.add("d-none");
    table.innerHTML = '<tr><td colspan="6" class="text-center py-4">Loading...</td></tr>';

    const params = new URLSearchParams();
    params.set("page", page);
    params.set("page_size", "20");

    const ticketId = document.getElementById("ticketIdFilter").value.trim();
    const attendee = document.getElementById("attendeeFilter").value.trim();
    const eventId = document.getElementById("eventFilter").value;
    const date = document.getElementById("dateFilter").value;
    if (ticketId) params.set("ticket_id", ticketId);
    if (attendee) params.set("attendee", attendee);
    if (eventId) params.set("event_id", eventId);
    if (date) params.set("checked_in_date", date);

    try {
        const data = await gateHistoryRequest(`/gate/check-ins?${params}`);
        if (!data.check_ins.length) {
            table.innerHTML =
                '<tr><td colspan="6" class="text-center text-muted py-5">No check-in records match these filters.</td></tr>';
        } else {
            table.innerHTML = data.check_ins.map(record => `
                <tr>
                    <td><strong>#${record.ticket_id}</strong></td>
                    <td>${escapeHistory(record.event_title)}</td>
                    <td>
                        <strong>${escapeHistory(record.attendee_name)}</strong>
                        <small class="d-block text-muted">${escapeHistory(record.attendee_email)}</small>
                    </td>
                    <td>${escapeHistory(formatHistoryDate(record.checked_in_at))}</td>
                    <td>${escapeHistory(record.staff_name || "Unknown")}</td>
                    <td><span class="status-badge status-used">Checked in</span></td>
                </tr>`).join("");
        }

        const pagination = document.getElementById("historyPagination");
        pagination.innerHTML = "";
        for (let i = 1; i <= data.total_pages; i++) {
            const item = document.createElement("li");
            item.className = `page-item${i === page ? " active" : ""}`;
            const button = document.createElement("button");
            button.className = "page-link";
            button.textContent = i;
            button.type = "button";
            button.addEventListener("click", () => loadHistory(i));
            item.appendChild(button);
            pagination.appendChild(item);
        }
    } catch (err) {
        table.innerHTML = "";
        error.textContent = err.message;
        error.classList.remove("d-none");
    }
}

document.getElementById("historyFilters").addEventListener("submit", event => {
    event.preventDefault();
    loadHistory(1);
});

loadEvents();
loadHistory();
