const token = EventSphereAuth.getToken();

if (!token) {
    window.location.href = "/ui/login";
}

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;",
        '"': "&quot;", "'": "&#039;"
    })[character]);
}

function formatDate(value) {
    if (!value) return "Not available";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "Not available" : date.toLocaleString();
}

function showMessage(text, type = "danger") {
    const element = document.getElementById("pageMessage");
    element.textContent = text;
    element.className = `alert alert-${type}`;
}

async function loadBookings() {
    const response = await fetch("/bookings/my-bookings", {
        headers: { "Authorization": `Bearer ${token}` }
    });

    if (response.status === 401) {
        EventSphereAuth.redirectToLogin();
        return;
    }

    if (response.status === 403) {
        showMessage("You do not have permission to view bookings.");
        return;
    }

    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Could not load bookings.");

    const bookings = data.bookings || [];
    document.getElementById("loading").classList.add("d-none");

    if (!bookings.length) {
        document.getElementById("emptyState").classList.remove("d-none");
        return;
    }

    document.getElementById("bookingList").innerHTML = bookings.map(booking => {
        const status = booking.booking_status || booking.status || "UNKNOWN";
        const statusClass = status === "CONFIRMED" ? "success"
            : status === "CANCELLED" ? "secondary" : "warning";
        return `
            <div class="col-md-6 col-lg-4">
                <article class="card h-100 shadow-sm">
                    <div class="card-body">
                        <h2 class="h5">${escapeHTML(booking.event_title || "Event")}</h2>
                        <p class="mb-1"><strong>Booking:</strong> #${escapeHTML(booking.booking_id)}</p>
                        <p class="mb-1"><strong>Quantity:</strong> ${escapeHTML(booking.quantity)}</p>
                        <p class="mb-1"><strong>Amount:</strong> LKR ${escapeHTML(booking.total_amount)}</p>
                        <p class="mb-1"><strong>Payment:</strong> ${escapeHTML(booking.payment_status || "Not available")}</p>
                        <p class="mb-1"><strong>Date:</strong> ${escapeHTML(formatDate(booking.created_at))}</p>
                        <span class="badge text-bg-${statusClass}">${escapeHTML(status)}</span>
                        ${status === "CONFIRMED" ? `
                            <button class="btn btn-outline-danger btn-sm mt-3"
                                    data-booking-id="${escapeHTML(booking.booking_id)}">
                                Cancel booking
                            </button>` : ""}
                    </div>
                </article>
            </div>`;
    }).join("");
}

document.getElementById("bookingList").addEventListener("click", async event => {
    const button = event.target.closest("[data-booking-id]");
    if (!button) return;

    const bookingId = button.dataset.bookingId;
    if (!window.confirm(`Cancel booking #${bookingId}? This will refund the payment.`)) {
        return;
    }

    button.disabled = true;
    try {
        const response = await fetch(`/bookings/${encodeURIComponent(bookingId)}/cancel`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Could not cancel booking.");
        showMessage("Booking cancelled and payment refunded.", "success");
        await loadBookings();
    } catch (error) {
        button.disabled = false;
        showMessage(error.message);
    }
});

document.getElementById("logoutButton").addEventListener("click", () => {
    EventSphereAuth.clearSession();
    window.location.href = "/ui/login";
});

loadBookings().catch(error => {
    document.getElementById("loading").classList.add("d-none");
    showMessage(error.message);
});
