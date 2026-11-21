
const token = sessionStorage.getItem("access_token");

if (!token) {
    window.location.href = "/ui/login";
}

async function apiGet(url) {
    const response = await fetch(url, {
        headers: {
            "Authorization": `Bearer ${token}`
        }
    });

    if (response.status === 401 || response.status === 403) {
        throw new Error("Admin access denied. Please login with an admin account.");
    }

    if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
    }

    return response.json();
}

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[char]);
}

function showError(message) {
    const element = document.getElementById("errorMessage");
    element.textContent = message;
    element.classList.remove("d-none");
}

function formatDate(value) {
    if (!value) return "N/A";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "N/A" : date.toLocaleString();
}

function statusBadge(value) {
    const status = String(value || "UNKNOWN").toUpperCase();
    return `<span class="status-badge status-${status.toLowerCase()}">${escapeHTML(status)}</span>`;
}

async function loadSummary() {
    const data = await apiGet("/dashboard/admin/summary");

    document.getElementById("totalUsers").textContent = data.total_users;
    document.getElementById("totalVenues").textContent = data.total_venues;
    document.getElementById("totalEvents").textContent = data.total_events;
    document.getElementById("publishedEvents").textContent =
        `${data.published_events} published`;
    document.getElementById("totalBookings").textContent = data.total_bookings;
    document.getElementById("confirmedBookings").textContent =
        `${data.confirmed_bookings} confirmed`;
    document.getElementById("totalRevenue").textContent =
        Number(data.total_revenue).toLocaleString("en-US");
    document.getElementById("totalTickets").textContent = data.total_tickets;
    document.getElementById("checkedInTickets").textContent =
        data.checked_in_tickets;
    document.getElementById("capacityInfo").textContent =
        `Published ticket capacity: ${data.total_capacity}`;
}

async function loadRecentEvents() {
    const data = await apiGet("/dashboard/admin/recent-events");
    const table = document.getElementById("eventTable");

    if (!data.events.length) {
        table.innerHTML = `<tr><td colspan="5"><div class="dashboard-empty"><i class="bi bi-calendar2-x"></i>No recent events found.</div></td></tr>`;
        return;
    }

    table.innerHTML = data.events.map(event => `
        <tr>
            <td>${escapeHTML(event.title)}</td>
            <td>${escapeHTML(event.category)}</td>
            <td>${escapeHTML(event.venue_name || "N/A")}</td>
            <td>${escapeHTML(formatDate(event.start_time))}</td>
            <td>${statusBadge(event.status)}</td>
        </tr>
    `).join("");
}

async function loadAgentMessages() {
    const data = await apiGet("/dashboard/admin/agent-messages");
    const table = document.getElementById("agentTable");

    if (!data.messages.length) {
        table.innerHTML = `<tr><td colspan="5"><div class="dashboard-empty"><i class="bi bi-chat-square-text"></i>No agent activity has been recorded.</div></td></tr>`;
        return;
    }

    table.innerHTML = data.messages.map(message => {
        let content = message.content;

        if (typeof content === "object") {
            content = JSON.stringify(content);
        }

        return `
            <tr>
                <td>${escapeHTML(message.sender)}</td>
                <td>${escapeHTML(message.receiver)}</td>
                <td>${escapeHTML(message.performative)}</td>
                <td class="text-break">${escapeHTML(content)}</td>
                <td>${escapeHTML(formatDate(message.created_at))}</td>
            </tr>
        `;
    }).join("");
}

async function loadRecentBookings() {
    const data = await apiGet("/dashboard/admin/recent-bookings");
    const table = document.getElementById("bookingTable");

    if (!data.bookings.length) {
        table.innerHTML = `<tr><td colspan="6"><div class="dashboard-empty"><i class="bi bi-journal-x"></i>No recent bookings found.</div></td></tr>`;
        return;
    }

    table.innerHTML = data.bookings.map(booking => `
        <tr>
            <td>#${escapeHTML(booking.booking_id)}</td>
            <td>${escapeHTML(booking.event_title)}</td>
            <td>${escapeHTML(booking.quantity)}</td>
            <td>LKR ${escapeHTML(booking.total_amount)}</td>
            <td>${statusBadge(booking.status)}</td>
            <td>${escapeHTML(formatDate(booking.created_at))}</td>
        </tr>
    `).join("");
}

async function loadDashboard() {
    document.getElementById("errorMessage").classList.add("d-none");

    try {
        await Promise.all([
            loadSummary(),
            loadRecentEvents(),
            loadAgentMessages(),
            loadRecentBookings()
        ]);
    } catch (error) {
        showError(error.message);
    }
}

function logout() {
    sessionStorage.clear();
    window.location.href = "/ui/login";
}

loadDashboard();
