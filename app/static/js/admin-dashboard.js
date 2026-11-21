
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
    if (Number.isNaN(date.getTime())) return "N/A";
    return date.toLocaleString("en-US", {
        year: "numeric",
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit"
    });
}

function formatDateParts(value) {
    if (!value) return { date: "N/A", time: "" };
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return { date: "N/A", time: "" };
    return {
        date: date.toLocaleString("en-US", { year: "numeric", month: "short", day: "2-digit" }),
        time: date.toLocaleString("en-US", { hour: "2-digit", minute: "2-digit" })
    };
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
    const table = document.getElementById("agentTable");
    table.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">Loading agent activity...</td></tr>`;

    try {
        const data = await apiGet("/dashboard/admin/agent-messages");
        window.agentMessages = Array.isArray(data.messages) ? data.messages : [];
        renderAgentOverview(window.agentMessages);
        populateAgentFilters(window.agentMessages);
        renderAgentMessages(window.agentMessages);
    } catch (error) {
        table.innerHTML = `
            <tr><td colspan="6">
                <div class="dashboard-empty">
                    <i class="bi bi-exclamation-circle"></i>
                    <strong>Agent activity could not be loaded.</strong>
                    <p class="text-muted mb-3">${escapeHTML(error.message)}</p>
                    <button class="btn btn-outline-primary btn-sm" type="button" onclick="loadAgentMessages()">
                        <i class="bi bi-arrow-clockwise me-1"></i> Retry
                    </button>
                </div>
            </td></tr>`;
    }
}

function parseMessageContent(message) {
    if (message.content && typeof message.content === "object") {
        return message.content;
    }
    if (typeof message.content === "string") {
        try {
            return JSON.parse(message.content);
        } catch {
            return message.content;
        }
    }
    return message.content ?? {};
}

function summarizeAgentMessage(message) {
    const content = parseMessageContent(message);
    if (typeof content === "string") return content;

    const action = content.action;
    if (action === "EXPIRE_WAITLIST") {
        if (typeof content.expired_count === "number") {
            return `Waitlist expiry completed – ${content.expired_count} expired entries`;
        }
        return "Automatic waitlist expiry check";
    }
    if (content.success === true) return "Agent operation completed successfully";
    if (content.reason) return String(content.reason);
    if (content.message) return String(content.message);
    if (action) return `Action: ${action.replaceAll("_", " ").toLowerCase()}`;
    return "Agent message received";
}

function performativeBadge(value) {
    const type = String(value || "UNKNOWN").toUpperCase();
    const className = {
        INFORM: "inform",
        AGREE: "agree",
        REQUEST: "request",
        CONFIRM: "confirm",
        REFUSE: "refuse",
        FAILURE: "failure",
        PROPOSE: "propose"
    }[type] || "unknown";
    return `<span class="performative-badge performative-${className}">${escapeHTML(type)}</span>`;
}

function renderAgentOverview(messages) {
    const container = document.getElementById("agentOverview");
    const agents = ["VenueAgent", "BookingAgent", "TicketAgent", "WaitlistAgent", "NotificationAgent"];
    container.innerHTML = agents.map(name => {
        const matching = messages.filter(message =>
            message.sender === name || message.receiver === name
        );
        const latest = matching[0];
        const status = latest ? "Recent activity" : "No recent activity";
        const icon = {
            VenueAgent: "bi-building",
            BookingAgent: "bi-journal-check",
            TicketAgent: "bi-ticket-perforated",
            WaitlistAgent: "bi-list-check",
            NotificationAgent: "bi-bell"
        }[name];
        return `
            <div class="col-6 col-xl">
                <div class="card agent-overview-card h-100">
                    <div class="card-body">
                        <span class="agent-overview-icon"><i class="bi ${icon}"></i></span>
                        <h6>${escapeHTML(name)}</h6>
                        <small class="${latest ? "text-primary" : "text-muted"}">${status}</small>
                    </div>
                </div>
            </div>`;
    }).join("");
}

function populateAgentFilters(messages) {
    const sender = document.getElementById("agentSenderFilter");
    const type = document.getElementById("agentTypeFilter");
    const senderValues = [...new Set(messages.map(message => message.sender).filter(Boolean))].sort();
    const typeValues = [...new Set(messages.map(message => message.performative).filter(Boolean))].sort();
    sender.innerHTML = '<option value="">All senders</option>' +
        senderValues.map(value => `<option value="${escapeHTML(value)}">${escapeHTML(value)}</option>`).join("");
    type.innerHTML = '<option value="">All message types</option>' +
        typeValues.map(value => `<option value="${escapeHTML(value)}">${escapeHTML(value)}</option>`).join("");
}

function filteredAgentMessages() {
    const messages = window.agentMessages || [];
    const search = document.getElementById("agentSearch").value.trim().toLowerCase();
    const sender = document.getElementById("agentSenderFilter").value;
    const type = document.getElementById("agentTypeFilter").value;
    return messages.filter(message => {
        const summary = summarizeAgentMessage(message).toLowerCase();
        const matchesSearch = !search ||
            summary.includes(search) ||
            String(message.sender || "").toLowerCase().includes(search) ||
            String(message.receiver || "").toLowerCase().includes(search);
        return matchesSearch &&
            (!sender || message.sender === sender) &&
            (!type || message.performative === type);
    });
}

function renderAgentMessages(messages) {
    const table = document.getElementById("agentTable");
    if (!messages.length) {
        table.innerHTML = `<tr><td colspan="6"><div class="dashboard-empty"><i class="bi bi-chat-square-text"></i>No agent activity matches this view.</div></td></tr>`;
        return;
    }
    table.innerHTML = messages.map((message, index) => {
        const parts = formatDateParts(message.created_at);
        const summary = summarizeAgentMessage(message);
        return `
            <tr>
                <td class="agent-name">${escapeHTML(message.sender || "Unknown")}</td>
                <td class="agent-name">${escapeHTML(message.receiver || "Unknown")}</td>
                <td>${performativeBadge(message.performative)}</td>
                <td class="agent-summary" title="${escapeHTML(summary)}">${escapeHTML(summary)}</td>
                <td class="agent-timestamp"><span>${escapeHTML(parts.date)}</span><small>${escapeHTML(parts.time)}</small></td>
                <td class="agent-actions">
                    <button class="btn btn-outline-primary btn-sm" type="button" data-agent-index="${index}" onclick="showAgentDetails(${index})">
                        <i class="bi bi-eye me-1"></i>View Details
                    </button>
                </td>
            </tr>`;
    }).join("");
    window.agentMessagesForView = messages;
}

window.showAgentDetails = function(index) {
    const message = window.agentMessagesForView?.[index];
    if (!message) return;
    const parts = formatDateParts(message.created_at);
    document.getElementById("agentDetailsMeta").innerHTML = `
        <div><strong>Sender</strong><span>${escapeHTML(message.sender || "Unknown")}</span></div>
        <div><strong>Receiver</strong><span>${escapeHTML(message.receiver || "Unknown")}</span></div>
        <div><strong>Message Type</strong>${performativeBadge(message.performative)}</div>
        <div><strong>Time</strong><span>${escapeHTML(parts.date)} · ${escapeHTML(parts.time)}</span></div>`;
    const content = parseMessageContent(message);
    document.getElementById("agentDetailsJson").textContent =
        typeof content === "string"
            ? content
            : JSON.stringify(content, null, 2);
    bootstrap.Modal.getOrCreateInstance(document.getElementById("agentDetailsModal")).show();
};

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

["agentSearch", "agentSenderFilter", "agentTypeFilter"].forEach(id => {
    const element = document.getElementById(id);
    if (element) {
        element.addEventListener(id === "agentSearch" ? "input" : "change", () => {
            renderAgentMessages(filteredAgentMessages());
        });
    }
});

loadDashboard();
