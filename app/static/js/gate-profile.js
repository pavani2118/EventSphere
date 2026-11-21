const token = sessionStorage.getItem("access_token") || localStorage.getItem("access_token");

function gateLogout() {
    sessionStorage.clear();
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    window.location.href = "/ui/login";
}

document.getElementById("gateLogout")?.addEventListener("click", gateLogout);
if (!token) window.location.href = "/ui/login";

async function loadGateProfile() {
    const profile = document.getElementById("gateProfile");
    const error = document.getElementById("gateProfileError");
    try {
        const response = await fetch("/auth/me", {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (response.status === 401) gateLogout();
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Could not load profile.");
        if (data.role !== "GATE_STAFF" && data.role !== "ADMIN") {
            throw new Error("Gate Staff or Admin access is required.");
        }
        profile.innerHTML = `
            <dt class="col-sm-4">Name</dt><dd class="col-sm-8">${data.full_name || "-"}</dd>
            <dt class="col-sm-4">Email</dt><dd class="col-sm-8">${data.email || "-"}</dd>
            <dt class="col-sm-4">Role</dt><dd class="col-sm-8"><span class="status-badge status-published">${data.role}</span></dd>`;
    } catch (err) {
        error.textContent = err.message;
        error.classList.remove("d-none");
    }
}

loadGateProfile();
