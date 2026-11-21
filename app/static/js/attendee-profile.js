const token = EventSphereAuth.getToken();
const user = EventSphereAuth.getUser();

if (!token) EventSphereAuth.redirectToLogin();

document.getElementById("logoutButton").addEventListener("click", () => {
    EventSphereAuth.clearSession();
    window.location.href = "/ui/login";
});

async function loadProfile() {
    const profile = document.getElementById("attendeeProfile");
    const error = document.getElementById("profileError");
    try {
        const response = await fetch("/auth/me", {
            headers: EventSphereAuth.authHeaders()
        });
        if (response.status === 401) {
            EventSphereAuth.redirectToLogin();
            return;
        }
        if (response.status === 403) {
            throw new Error("Your account does not have permission to view this profile.");
        }
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Could not load profile.");
        if (data.role !== "ATTENDEE") {
            throw new Error("Attendee profile access is required.");
        }
        profile.innerHTML = `
            <dt class="col-sm-4">Name</dt><dd class="col-sm-8">${data.full_name || "-"}</dd>
            <dt class="col-sm-4">Email</dt><dd class="col-sm-8">${data.email || "-"}</dd>
            <dt class="col-sm-4">Role</dt><dd class="col-sm-8"><span class="status-badge status-confirmed">${data.role}</span></dd>
        `;
    } catch (err) {
        error.textContent = err.message;
        error.classList.remove("d-none");
    }
}

loadProfile();
