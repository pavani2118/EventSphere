const token = sessionStorage.getItem("access_token");

if (!token) window.location.href = "/ui/login";

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;",
        '"': "&quot;", "'": "&#039;"
    })[character]);
}

function formatDate(value) {
    const date = new Date(value);
    return value && !Number.isNaN(date.getTime()) ? date.toLocaleString() : "Not available";
}

function statusClass(status) {
    return {
        WAITING: "warning", FULFILLED: "success",
        EXPIRED: "secondary", CANCELLED: "dark"
    }[status] || "secondary";
}

async function loadWaitlist() {
    const response = await fetch("/waitlist/my-waitlist", {
        headers: { "Authorization": `Bearer ${token}` }
    });
    if (response.status === 401 || response.status === 403) {
        sessionStorage.clear();
        window.location.href = "/ui/login";
        return;
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Could not load waitlist.");

    document.getElementById("loading").classList.add("d-none");
    const entries = data.waitlist || [];
    if (!entries.length) {
        document.getElementById("emptyState").classList.remove("d-none");
        return;
    }
    document.getElementById("waitlistList").innerHTML = entries.map(entry => `
        <div class="col-md-6 col-lg-4">
            <article class="card h-100 shadow-sm">
                <div class="card-body">
                    <h2 class="h5">${escapeHTML(entry.event_title || `Event #${entry.event_id}`)}</h2>
                    <p class="mb-1"><strong>Quantity:</strong> ${escapeHTML(entry.quantity)}</p>
                    <p class="mb-1"><strong>Joined:</strong> ${escapeHTML(formatDate(entry.created_at))}</p>
                    <span class="badge text-bg-${statusClass(entry.status)}">${escapeHTML(entry.status)}</span>
                </div>
            </article>
        </div>`).join("");
}

document.getElementById("logoutButton").addEventListener("click", () => {
    sessionStorage.clear();
    window.location.href = "/ui/login";
});

loadWaitlist().catch(error => {
    document.getElementById("loading").classList.add("d-none");
    const message = document.getElementById("pageMessage");
    message.textContent = error.message;
    message.className = "alert alert-danger";
});
