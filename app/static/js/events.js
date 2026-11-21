const eventList = document.getElementById("eventList");
const loading = document.getElementById("loading");
const noEvents = document.getElementById("noEvents");
const eventCount = document.getElementById("eventCount");
const searchInput = document.getElementById("searchInput");
const categoryFilter = document.getElementById("categoryFilter");

let allEvents = [];

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[char]);
}

function formatDate(value) {
    if (!value) return "Date not available";

    return new Date(value).toLocaleString("en-US", {
        dateStyle: "medium",
        timeStyle: "short"
    });
}

async function loadEvents() {
    try {
        const response = await fetch("/events/");

        if (!response.ok) {
            throw new Error("Unable to load events.");
        }

        const data = await response.json();

        allEvents = data.events || [];

        loading.classList.add("d-none");

        populateCategories();
        filterEvents();

    } catch (error) {
        loading.textContent = error.message;
    }
}

function populateCategories() {
    const categories = [...new Set(
        allEvents.map(event => event.category).filter(Boolean)
    )];

    categories.forEach(category => {
        const option = document.createElement("option");

        option.value = category;
        option.textContent = category;

        categoryFilter.appendChild(option);
    });

    const requestedCategory =
        new URLSearchParams(window.location.search).get("category");

    if (requestedCategory) {
        const matchingCategory = categories.find(
            category => category.toLowerCase() === requestedCategory.toLowerCase()
        );

        if (matchingCategory) {
            categoryFilter.value = matchingCategory;
        }
    }
}

function displayEvents(events) {
    eventList.innerHTML = "";

    eventCount.textContent = `${events.length} event(s) found`;

    if (events.length === 0) {
        noEvents.classList.remove("d-none");
        return;
    }

    noEvents.classList.add("d-none");

    events.forEach(event => {

        const card = document.createElement("div");

        card.className = "col-md-6 col-lg-4";

        card.innerHTML = `
            <div class="card event-card h-100 shadow-sm">
                <div class="card-body d-flex flex-column">

                    <span class="badge bg-primary align-self-start mb-3">
                        ${escapeHTML(event.category || "Event")}
                    </span>

                    <h5 class="card-title fw-bold">
                        ${escapeHTML(event.title)}
                    </h5>

                    <p class="text-muted mb-2">
                        <strong>Venue:</strong>
                        ${escapeHTML(event.venue_name)}
                    </p>

                    <p class="text-muted mb-2">
                        <strong>Location:</strong>
                        ${escapeHTML(event.venue_location)}
                    </p>

                    <p class="text-muted mb-2">
                        <strong>Starts:</strong>
                        ${escapeHTML(formatDate(event.start_time))}
                    </p>

                    <p class="text-muted mb-3">
                        <strong>Ends:</strong>
                        ${escapeHTML(formatDate(event.end_time))}
                    </p>

                    <p class="card-text">
                        ${escapeHTML(event.description || "No description available.")}
                    </p>

                    <button
                        class="btn btn-outline-primary mt-auto"
                        onclick="viewEvent(${Number(event.id)})">
                        View Details
                    </button>

                </div>
            </div>
        `;

        eventList.appendChild(card);
    });
}

function viewEvent(eventId) {
    window.location.href = `/ui/event/${eventId}`;
}

function filterEvents() {
    const searchValue = searchInput.value.toLowerCase().trim();
    const selectedCategory = categoryFilter.value.toLowerCase();

    const filtered = allEvents.filter(event => {

        const matchesTitle = (event.title || "")
            .toLowerCase()
            .includes(searchValue);

        const matchesCategory = !selectedCategory ||
            (event.category || "").toLowerCase() === selectedCategory;

        return matchesTitle && matchesCategory;
    });

    displayEvents(filtered);
}

searchInput.addEventListener("input", filterEvents);

categoryFilter.addEventListener("change", filterEvents);

loadEvents();