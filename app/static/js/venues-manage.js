
const API_URL = "/venues";
const token = sessionStorage.getItem("access_token");

if (!token) {
    window.location.href = "/ui/login";
}

function logout() {
    sessionStorage.clear();
    window.location.href = "/ui/login";
}

function showMessage(message, type = "success") {
    const box = document.getElementById("message");
    box.textContent = message;
    box.className = `alert alert-${type}`;
    window.scrollTo({ top: 0, behavior: "smooth" });
}

async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`,
            ...(options.headers || {})
        }
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(data.detail || "Request failed");
    }

    return data;
}

async function loadVenues() {
    const loading = document.getElementById("loading");
    const table = document.getElementById("venueTable");
    const empty = document.getElementById("emptyMessage");

    loading.classList.remove("d-none");
    table.innerHTML = "";
    empty.classList.add("d-none");

    try {
        const result = await apiRequest(API_URL);
        const venues = Array.isArray(result)
            ? result
            : (result.venues || result.items || []);

        loading.classList.add("d-none");

        if (venues.length === 0) {
            empty.classList.remove("d-none");
            return;
        }

        venues.forEach(venue => {
            const row = document.createElement("tr");

            const name = document.createElement("td");
            name.textContent = venue.name ?? "";

            const location = document.createElement("td");
            location.textContent = venue.location ?? "";

            const capacity = document.createElement("td");
            capacity.textContent = venue.capacity ?? "";

            const rate = document.createElement("td");
            rate.textContent = `LKR ${venue.hourly_rate ?? 0}`;

            const hire = document.createElement("td");
            hire.textContent = venue.private_hire_available ? "Available" : "No";

            const actions = document.createElement("td");

            const edit = document.createElement("button");
            edit.className = "btn btn-sm btn-warning me-2";
            edit.textContent = "Edit";
            edit.addEventListener("click", () => editVenue(venue));

            const remove = document.createElement("button");
            remove.className = "btn btn-sm btn-danger";
            remove.textContent = "Delete";
            remove.addEventListener("click", () => deleteVenue(venue.id));

            actions.append(edit, remove);
            row.append(name, location, capacity, rate, hire, actions);
            table.appendChild(row);
        });

    } catch (error) {
        loading.classList.add("d-none");
        showMessage(error.message, "danger");
    }
}

function openAddForm() {
    document.getElementById("venueForm").reset();
    document.getElementById("venueId").value = "";
    document.getElementById("formTitle").textContent = "Add New Venue";
    document.getElementById("saveButton").textContent = "Save Venue";
    document.getElementById("venueFormCard").style.display = "block";
    window.scrollTo({ top: 0, behavior: "smooth" });
}

function closeForm() {
    document.getElementById("venueFormCard").style.display = "none";
}

function editVenue(venue) {
    document.getElementById("venueId").value = venue.id;
    document.getElementById("venueName").value = venue.name ?? "";
    document.getElementById("venueLocation").value = venue.location ?? "";
    document.getElementById("venueCapacity").value = venue.capacity ?? 1;
    document.getElementById("venueRate").value = venue.hourly_rate ?? 0;
    document.getElementById("venueDescription").value = venue.description ?? "";
    document.getElementById("privateHire").value =
        String(Boolean(venue.private_hire_available));

    document.getElementById("formTitle").textContent = "Edit Venue";
    document.getElementById("saveButton").textContent = "Update Venue";
    document.getElementById("venueFormCard").style.display = "block";
    window.scrollTo({ top: 0, behavior: "smooth" });
}

document.getElementById("venueForm").addEventListener("submit", async function(event) {
    event.preventDefault();

    const id = document.getElementById("venueId").value;

    const venueData = {
        name: document.getElementById("venueName").value.trim(),
        location: document.getElementById("venueLocation").value.trim(),
        capacity: Number(document.getElementById("venueCapacity").value),
        hourly_rate: Number(document.getElementById("venueRate").value),
        description: document.getElementById("venueDescription").value.trim(),
        private_hire_available:
            document.getElementById("privateHire").value === "true"
    };

    try {
        const button = document.getElementById("saveButton");
        button.disabled = true;

        if (id) {
            await apiRequest(`${API_URL}/${id}`, {
                method: "PUT",
                body: JSON.stringify(venueData)
            });
            showMessage("Venue updated successfully!");
        } else {
            await apiRequest(`${API_URL}/`, {
                method: "POST",
                body: JSON.stringify(venueData)
            });
            showMessage("Venue added successfully!");
        }

        closeForm();
        await loadVenues();

    } catch (error) {
        showMessage(error.message, "danger");
    } finally {
        document.getElementById("saveButton").disabled = false;
    }
});

async function deleteVenue(id) {
    if (!confirm("Are you sure you want to delete this venue?")) return;

    try {
        await apiRequest(`${API_URL}/${id}`, { method: "DELETE" });
        showMessage("Venue deleted successfully!");
        await loadVenues();
    } catch (error) {
        showMessage(error.message, "danger");
    }
}

loadVenues();
