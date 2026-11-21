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

async function loadNotifications() {
    const response = await fetch("/notifications/my-notifications", {
        headers: { "Authorization": `Bearer ${token}` }
    });
    if (response.status === 401 || response.status === 403) {
        sessionStorage.clear();
        window.location.href = "/ui/login";
        return;
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Could not load notifications.");

    document.getElementById("notificationSummary").textContent =
        `${data.total_notifications} notification(s), ${data.unread_notifications} unread`;
    const notifications = data.notifications || [];
    if (!notifications.length) {
        document.getElementById("emptyState").classList.remove("d-none");
        return;
    }
    document.getElementById("notificationList").innerHTML = notifications.map(item => `
        <article class="list-group-item ${item.is_read ? "" : "list-group-item-primary"}">
            <div class="d-flex justify-content-between gap-3">
                <p class="mb-1">${escapeHTML(item.message)}</p>
                <small class="text-nowrap">${escapeHTML(formatDate(item.created_at))}</small>
            </div>
            <small class="text-muted">
                ${item.is_read ? "Read" : `
                    <button class="btn btn-link btn-sm p-0"
                            data-notification-id="${escapeHTML(item.id)}">
                        Mark as read
                    </button>`}
            </small>
        </article>`).join("");
}

document.getElementById("notificationList").addEventListener("click", async event => {
    const button = event.target.closest("[data-notification-id]");
    if (!button) return;

    button.disabled = true;
    try {
        const response = await fetch(
            `/notifications/${encodeURIComponent(button.dataset.notificationId)}/read`,
            {
                method: "PATCH",
                headers: { "Authorization": `Bearer ${token}` }
            }
        );
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Could not update notification.");
        await loadNotifications();
    } catch (error) {
        button.disabled = false;
        const message = document.getElementById("pageMessage");
        message.textContent = error.message;
        message.className = "alert alert-danger";
    }
});

document.getElementById("logoutButton").addEventListener("click", () => {
    sessionStorage.clear();
    window.location.href = "/ui/login";
});

document.getElementById("markAllRead").addEventListener("click", async () => {
    const button = document.getElementById("markAllRead");
    button.disabled = true;
    try {
        const response = await fetch("/notifications/mark-all-read", {
            method: "PATCH",
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Could not update notifications.");
        await loadNotifications();
    } catch (error) {
        const message = document.getElementById("pageMessage");
        message.textContent = error.message;
        message.className = "alert alert-danger";
    } finally {
        button.disabled = false;
    }
});

loadNotifications().catch(error => {
    const message = document.getElementById("pageMessage");
    message.textContent = error.message;
    message.className = "alert alert-danger";
});
