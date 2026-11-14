
const API_BASE = "";

const token = sessionStorage.getItem("access_token");

if (!token) {
    window.location.href = "/ui/login";
}

async function apiRequest(url) {
    const response = await fetch(`${API_BASE}${url}`, {
        method: "GET",
        headers: {
            "Authorization": `Bearer ${token}`
        }
    });

    if (response.status === 401 || response.status === 403) {
        sessionStorage.clear();
        window.location.href = "/ui/login";
        throw new Error("Please log in again.");
    }

    if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
    }

    return response.json();
}

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[character]);
}

function formatDate(value) {
    if (!value) return "Not available";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return escapeHTML(value);
    }

    return date.toLocaleString();
}

function showMessage(message, type = "danger") {
    const element = document.getElementById("pageMessage");
    element.textContent = message;
    element.className = `alert alert-${type}`;
}

function getArray(data, possibleKeys) {
    if (Array.isArray(data)) return data;

    for (const key of possibleKeys) {
        if (Array.isArray(data?.[key])) {
            return data[key];
        }
    }

    return [];
}

// -------------------------
// LOAD BOOKINGS
// -------------------------

async function loadBookings() {
    const loading = document.getElementById("bookingLoading");
    const list = document.getElementById("bookingList");
    const empty = document.getElementById("noBookings");

    try {
        const data = await apiRequest("/bookings/my-bookings");
        const bookings = getArray(data, ["bookings", "items", "results"]);

        loading.classList.add("d-none");

        if (bookings.length === 0) {
            empty.classList.remove("d-none");
            return;
        }

        list.innerHTML = bookings.map(booking => {
            const title = booking.event_title || booking.title || `Event #${booking.event_id ?? ""}`;
            const status = booking.status || "UNKNOWN";
            const paymentReference =
                booking.payment_reference ||
                booking.payment_ref ||
                "Not available";

            return `
                <div class="col-md-6">
                    <div class="card h-100 shadow-sm">
                        <div class="card-body">
                            <h5 class="card-title">${escapeHTML(title)}</h5>

                            <p class="mb-1">
                                <strong>Booking ID:</strong>
                                ${escapeHTML(booking.id ?? booking.booking_id ?? "N/A")}
                            </p>

                            <p class="mb-1">
                                <strong>Quantity:</strong>
                                ${escapeHTML(booking.quantity ?? "N/A")}
                            </p>

                            <p class="mb-1">
                                <strong>Total:</strong>
                                LKR ${escapeHTML(booking.total_amount ?? "0")}
                            </p>

                            <p class="mb-1">
                                <strong>Payment Reference:</strong>
                                ${escapeHTML(paymentReference)}
                            </p>

                            <p class="mb-0">
                                <strong>Status:</strong>
                                <span class="badge bg-success">
                                    ${escapeHTML(status)}
                                </span>
                            </p>
                        </div>
                    </div>
                </div>
            `;
        }).join("");

    } catch (error) {
        loading.classList.add("d-none");
        showMessage("Could not load bookings: " + error.message);
    }
}

// -------------------------
// LOAD TICKETS
// -------------------------

async function loadTickets() {
    const loading = document.getElementById("ticketLoading");
    const list = document.getElementById("ticketList");
    const empty = document.getElementById("noTickets");

    try {
        const data = await apiRequest("/tickets/my-tickets");
        const tickets = getArray(data, ["tickets", "items", "results"]);

        loading.classList.add("d-none");

        if (tickets.length === 0) {
            empty.classList.remove("d-none");
            return;
        }

        list.innerHTML = tickets.map(ticket => {
            const ticketId = ticket.id ?? ticket.ticket_id;
            const title = ticket.event_title || ticket.title ||
                `Event #${ticket.event_id ?? ""}`;
            const status = ticket.status || "UNKNOWN";

            return `
                <div class="col-md-6">
                    <div class="card h-100 shadow-sm ticket-card">
                        <div class="card-body text-center">
                            <h5>${escapeHTML(title)}</h5>

                            <p class="mb-1">
                                <strong>Ticket ID:</strong>
                                ${escapeHTML(ticketId ?? "N/A")}
                            </p>

                            <p class="mb-3">
                                <strong>Status:</strong>
                                <span class="badge ${
                                    status === "VALID" ? "bg-success" :
                                    status === "USED" ? "bg-secondary" : "bg-danger"
                                }">${escapeHTML(status)}</span>
                            </p>

                            <div id="qr-${escapeHTML(ticketId)}"
                                 class="qr-container mb-2">
                                Loading QR code...
                            </div>

                            <small class="text-muted">
                                Present this QR code at the entrance.
                            </small>
                        </div>
                    </div>
                </div>
            `;
        }).join("");

        // Load QR images after creating the ticket cards.
        for (const ticket of tickets) {
            const ticketId = ticket.id ?? ticket.ticket_id;

            if (ticketId !== undefined && ticketId !== null) {
                await loadQRCode(ticketId);
            }
        }

    } catch (error) {
        loading.classList.add("d-none");
        showMessage("Could not load tickets: " + error.message);
    }
}

// -------------------------
// LOAD ONE QR CODE
// -------------------------

async function loadQRCode(ticketId) {
    const container = document.getElementById(`qr-${ticketId}`);

    if (!container) return;

    try {
        const response = await fetch(`/tickets/${encodeURIComponent(ticketId)}/qr`, {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (!response.ok) {
            container.textContent = "QR code is not available.";
            return;
        }

        const imageBlob = await response.blob();
        const imageUrl = URL.createObjectURL(imageBlob);

        const image = document.createElement("img");
        image.src = imageUrl;
        image.alt = "Ticket QR Code";
        image.width = 180;
        image.height = 180;
        image.className = "img-fluid";

        container.textContent = "";
        container.appendChild(image);

    } catch (error) {
        container.textContent = "Could not load QR code.";
    }
}

// -------------------------
// LOGOUT
// -------------------------

function logout() {
    sessionStorage.removeItem("access_token");
    sessionStorage.removeItem("user");
    window.location.href = "/ui/login";
}

// -------------------------
// PAGE INITIALIZATION
// -------------------------

loadBookings();
loadTickets();
