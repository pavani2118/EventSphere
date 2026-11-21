const token = sessionStorage.getItem("access_token") || localStorage.getItem("access_token");
const user = JSON.parse(sessionStorage.getItem("user") || localStorage.getItem("user") || "null");

function organiserLogout() {
    sessionStorage.clear();
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    window.location.href = "/ui/login";
}

document.getElementById("organiserLogout")?.addEventListener("click", organiserLogout);
if (!token) window.location.href = "/ui/login";

function escapeOrganiser(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[character]);
}

async function organiserRequest(url) {
    const response = await fetch(url, {
        headers: { "Authorization": `Bearer ${token}` }
    });
    if (response.status === 401) organiserLogout();
    if (response.status === 403) throw new Error("Organiser access is required.");
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Could not load organiser data.");
    return data;
}

async function loadOrganiserSummary() {
    const error = document.getElementById("organiserError");
    error.classList.add("d-none");
    try {
        const data = await organiserRequest("/dashboard/organiser/summary");
        document.getElementById("organiserTotalEvents").textContent = data.total_events;
        document.getElementById("organiserPublishedEvents").textContent = data.published_events;
        document.getElementById("organiserTicketsSold").textContent = data.total_tickets;
        document.getElementById("organiserRevenue").textContent =
            `LKR ${Number(data.total_revenue).toLocaleString("en-US", { minimumFractionDigits: 2 })}`;

        const filter = document.getElementById("organiserEventFilter");
        if (filter.options.length === 1) {
            const eventMap = new Map();
            data.recent_bookings.forEach(booking => {
                eventMap.set(booking.event_id, booking.event_title);
            });
            eventMap.forEach((title, id) => {
                const option = document.createElement("option");
                option.value = id;
                option.textContent = title;
                filter.appendChild(option);
            });
        }
        await loadOrganiserBookings();
    } catch (err) {
        error.textContent = err.message;
        error.classList.remove("d-none");
    }
}

async function loadOrganiserBookings() {
    const table = document.getElementById("organiserBookings");
    table.innerHTML = '<tr><td colspan="7" class="text-center py-4">Loading bookings...</td></tr>';
    const eventId = document.getElementById("organiserEventFilter").value;
    const status = document.getElementById("organiserStatusFilter").value;
    const params = new URLSearchParams();
    if (eventId) params.set("event_id", eventId);
    if (status) params.set("status", status);

    try {
        const data = await organiserRequest(
            `/dashboard/organiser/bookings${params.toString() ? `?${params}` : ""}`
        );
        if (!data.bookings.length) {
            table.innerHTML =
                '<tr><td colspan="7" class="text-center text-muted py-5">No bookings match these filters.</td></tr>';
            return;
        }
        table.innerHTML = data.bookings.map(booking => `
            <tr>
                <td><strong>#${booking.booking_id}</strong></td>
                <td>${escapeOrganiser(booking.event_title)}</td>
                <td>
                    <strong>${escapeOrganiser(booking.attendee_name)}</strong>
                    <small class="d-block text-muted">${escapeOrganiser(booking.attendee_email)}</small>
                </td>
                <td>${booking.quantity}</td>
                <td>LKR ${Number(booking.total_amount).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
                <td><span class="status-badge ${booking.payment_status === "SUCCESS" ? "status-confirmed" : "status-pending"}">${escapeOrganiser(booking.payment_status || "PENDING")}</span></td>
                <td><span class="status-badge status-${String(booking.booking_status).toLowerCase()}">${escapeOrganiser(booking.booking_status)}</span></td>
            </tr>`).join("");
    } catch (err) {
        table.innerHTML =
            `<tr><td colspan="7" class="text-center text-danger py-4">${escapeOrganiser(err.message)}</td></tr>`;
    }
}

document.getElementById("organiserEventFilter").addEventListener("change", loadOrganiserBookings);
document.getElementById("organiserStatusFilter").addEventListener("change", loadOrganiserBookings);
document.getElementById("organiserRefresh").addEventListener("click", loadOrganiserSummary);

if (user?.full_name) {
    document.getElementById("organiserWelcome").textContent =
        `Welcome, ${user.full_name}`;
}

loadOrganiserSummary();
