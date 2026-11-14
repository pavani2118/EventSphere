
const API = "/events";
const LIST_API = "/events/manage/all";
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
        throw new Error(data.detail?.message || data.detail || "Request failed");
    }

    return data;
}


// LOAD VENUES

async function loadVenues() {
    const select = document.getElementById("eventVenue");

    try {
        const result = await apiRequest("/venues/");
        const venues = Array.isArray(result)
            ? result
            : (result.venues || result.items || []);

        select.innerHTML = '<option value="">Select a venue</option>';

        venues.forEach(venue => {
            const option = document.createElement("option");
            option.value = venue.id;
            option.textContent =
                `${venue.name} (Capacity: ${venue.capacity})`;
            select.appendChild(option);
        });

    } catch (error) {
        select.innerHTML =
            '<option value="">Could not load venues</option>';
        showMessage(error.message, "danger");
    }
}


// LOAD ALL EVENTS INCLUDING DRAFT

async function loadEvents() {
    const loading = document.getElementById("loading");
    const table = document.getElementById("eventTable");
    const empty = document.getElementById("emptyMessage");

    loading.classList.remove("d-none");
    table.innerHTML = "";
    empty.classList.add("d-none");

    try {
        const result = await apiRequest(LIST_API);

        const events = Array.isArray(result)
            ? result
            : (result.events || result.items || []);

        loading.classList.add("d-none");

        if (events.length === 0) {
            empty.classList.remove("d-none");
            return;
        }

        events.forEach(event => {
            const row = document.createElement("tr");

            const title = document.createElement("td");
            title.textContent = event.title ?? "";

            const category = document.createElement("td");
            category.textContent = event.category ?? "";

            const venue = document.createElement("td");
            venue.textContent =
                event.venue_name ?? event.venue_id ?? "—";

            const date = document.createElement("td");
            date.textContent = event.start_time
                ? new Date(event.start_time).toLocaleString()
                : "—";

            const status = document.createElement("td");
            status.textContent = event.status ?? "";

            const actions = document.createElement("td");

            if (event.status === "DRAFT") {
                const edit = document.createElement("button");
                edit.className =
                    "btn btn-sm btn-warning me-1 mb-1";
                edit.textContent = "Edit";
                edit.addEventListener(
                    "click",
                    () => editEvent(event)
                );

                const categories = document.createElement("button");
                categories.className =
                    "btn btn-sm btn-info me-1 mb-1";
                categories.textContent = "Tickets";
                categories.addEventListener(
                    "click",
                    () => manageCategories(event.id)
                );

                const publish = document.createElement("button");
                publish.className =
                    "btn btn-sm btn-success me-1 mb-1";
                publish.textContent = "Publish";
                publish.addEventListener(
                    "click",
                    () => publishEvent(event.id)
                );

                actions.append(edit, categories, publish);
            }

            if (event.status === "PUBLISHED") {
                const cancel = document.createElement("button");
                cancel.className =
                    "btn btn-sm btn-danger mb-1";
                cancel.textContent = "Cancel";
                cancel.addEventListener(
                    "click",
                    () => cancelEvent(event.id)
                );

                actions.appendChild(cancel);
            }

            row.append(
                title,
                category,
                venue,
                date,
                status,
                actions
            );

            table.appendChild(row);
        });

    } catch (error) {
        loading.classList.add("d-none");
        showMessage(error.message, "danger");
    }
}


// OPEN CREATE FORM

function openEventForm() {
    document.getElementById("eventForm").reset();
    document.getElementById("eventId").value = "";

    document.getElementById("formTitle").textContent =
        "Create New Event";

    document.getElementById("saveEventButton").textContent =
        "Save as Draft";

    document.getElementById("eventFormCard").style.display =
        "block";

    window.scrollTo({ top: 0, behavior: "smooth" });
}


// CLOSE FORM

function closeEventForm() {
    document.getElementById("eventFormCard").style.display =
        "none";
}


// CONVERT DATE

function toLocalDateTime(value) {
    const date = new Date(value);
    const offset = date.getTimezoneOffset();

    return new Date(date.getTime() - offset * 60000)
        .toISOString()
        .slice(0, 16);
}


// EDIT EVENT

function editEvent(event) {
    document.getElementById("eventId").value = event.id;

    document.getElementById("eventTitle").value =
        event.title ?? "";

    document.getElementById("eventCategory").value =
        event.category ?? "";

    document.getElementById("eventVenue").value =
        event.venue_id ?? "";

    document.getElementById("startTime").value =
        toLocalDateTime(event.start_time);

    document.getElementById("endTime").value =
        toLocalDateTime(event.end_time);

    document.getElementById("eventDescription").value =
        event.description ?? "";

    document.getElementById("formTitle").textContent =
        "Edit Event";

    document.getElementById("saveEventButton").textContent =
        "Update Event";

    document.getElementById("eventFormCard").style.display =
        "block";

    window.scrollTo({ top: 0, behavior: "smooth" });
}


// CREATE / UPDATE EVENT

document.getElementById("eventForm").addEventListener(
    "submit",
    async function(e) {
        e.preventDefault();

        const id = document.getElementById("eventId").value;

        const start =
            document.getElementById("startTime").value;

        const end =
            document.getElementById("endTime").value;

        if (new Date(end) <= new Date(start)) {
            showMessage(
                "End time must be after start time.",
                "danger"
            );
            return;
        }

        const eventData = {
            title: document.getElementById("eventTitle").value.trim(),
            category: document.getElementById("eventCategory").value,
            venue_id: Number(
                document.getElementById("eventVenue").value
            ),
            start_time: new Date(start).toISOString(),
            end_time: new Date(end).toISOString(),
            description:
                document.getElementById("eventDescription").value.trim()
        };

        const button =
            document.getElementById("saveEventButton");

        button.disabled = true;

        try {
            if (id) {
                await apiRequest(`${API}/${id}`, {
                    method: "PUT",
                    body: JSON.stringify(eventData)
                });

                showMessage("Event updated successfully!");

            } else {
                await apiRequest(`${API}/`, {
                    method: "POST",
                    body: JSON.stringify(eventData)
                });

                showMessage(
                    "Event created successfully as DRAFT!"
                );
            }

            closeEventForm();
            await loadEvents();

        } catch (error) {
            showMessage(error.message, "danger");

        } finally {
            button.disabled = false;
        }
    }
);


// PUBLISH EVENT

async function publishEvent(id) {
    if (!confirm("Publish this event?")) return;

    try {
        await apiRequest(`${API}/${id}/publish`, {
            method: "POST"
        });

        showMessage("Event published successfully!");
        await loadEvents();

    } catch (error) {
        showMessage(error.message, "danger");
    }
}


// CANCEL EVENT

async function cancelEvent(id) {
    if (!confirm("Are you sure you want to cancel this event?")) {
        return;
    }

    try {
        await apiRequest(`${API}/${id}/cancel`, {
            method: "POST"
        });

        showMessage("Event cancelled successfully!");
        await loadEvents();

    } catch (error) {
        showMessage(error.message, "danger");
    }
}


// TICKET CATEGORY MANAGEMENT PAGE

function manageCategories(eventId) {
    window.location.href =
        `/ui/manage-ticket-categories/${eventId}`;
}


// INITIALIZE

async function initializePage() {
    await loadVenues();
    await loadEvents();
}

initializePage();
