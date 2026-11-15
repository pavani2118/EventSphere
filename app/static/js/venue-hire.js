
const API_URL = "/venue-hire";

const token = sessionStorage.getItem("access_token");
const user = JSON.parse(sessionStorage.getItem("user") || "null");

const venueSelect = document.getElementById("venueId");
const form = document.getElementById("venueHireForm");
const message = document.getElementById("message");
const resultCard = document.getElementById("resultCard");
const resultContent = document.getElementById("resultContent");

const availabilityButton = document.getElementById(
    "checkAvailabilityButton"
);

const submitButton = document.getElementById("submitButton");

if (!token || !user) {
    window.location.href = "/ui/login";
}

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;",
        '"': "&quot;", "'": "&#039;"
    })[character]);
}

// -------------------------------------------------
// DISPLAY MESSAGES
// -------------------------------------------------

function showMessage(text, type = "info") {

    message.className = `alert alert-${type}`;
    message.textContent = text;
    message.classList.remove("d-none");
}

function getErrorMessage(data) {

    if (typeof data.detail === "string") {
        return data.detail;
    }

    if (Array.isArray(data.detail)) {
        return data.detail.map(item => {
            if (typeof item === "string") return item;
            return item.msg || JSON.stringify(item);
        }).join(", ");
    }

    if (typeof data.message === "string") {
        return data.message;
    }

    return "Something went wrong. Please try again.";
}

// -------------------------------------------------
// API REQUEST
// -------------------------------------------------

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
        throw new Error(getErrorMessage(data));
    }

    return data;
}

// -------------------------------------------------
// LOAD VENUES
// -------------------------------------------------

async function loadHireHistory() {
    const loading = document.getElementById("hireHistoryLoading");
    const list = document.getElementById("hireHistoryList");
    const empty = document.getElementById("hireHistoryEmpty");

    try {
        const data = await apiRequest("/venue-hire/my-requests");
        const requests = data.requests || [];
        loading.classList.add("d-none");

        if (!requests.length) {
            empty.classList.remove("d-none");
            return;
        }

        list.innerHTML = requests.map(request => `
            <div class="border rounded p-3 mb-2">
                <div class="d-flex justify-content-between gap-2">
                    <strong>${escapeHTML(request.venue_name)}</strong>
                    <span class="badge text-bg-secondary">${escapeHTML(request.status)}</span>
                </div>
                <div class="small text-muted">
                    ${escapeHTML(new Date(request.start_time).toLocaleString())} -
                    ${escapeHTML(new Date(request.end_time).toLocaleString())}
                    · ${escapeHTML(request.guest_count)} guests
                    · LKR ${escapeHTML(request.quoted_price)}
                </div>
            </div>
        `).join("");
    } catch (error) {
        loading.textContent = error.message;
        loading.className = "text-danger";
    }
}

async function loadVenues() {

    try {

        const data = await apiRequest("/venues/");

        const venues = Array.isArray(data)
            ? data
            : data.venues || data.items || [];

        venueSelect.innerHTML =
            '<option value="">Select a venue</option>';

        const availableVenues = venues.filter(
            venue => venue.private_hire_available === true
        );

        availableVenues.forEach(venue => {

            const option = document.createElement("option");

            option.value = venue.id;

            option.textContent =
                `${venue.name} - Capacity: ${venue.capacity} - ` +
                `LKR ${venue.hourly_rate}/hour`;

            option.dataset.capacity = venue.capacity;

            venueSelect.appendChild(option);
        });

        if (availableVenues.length === 0) {
            showMessage(
                "No venues are currently available for private hire.",
                "warning"
            );
        }

    } catch (error) {

        venueSelect.innerHTML =
            '<option value="">Unable to load venues</option>';

        showMessage(error.message, "danger");
    }
}

// -------------------------------------------------
// FORM DATA
// -------------------------------------------------

function getFormData() {

    const startValue = document.getElementById("startTime").value;
    const endValue = document.getElementById("endTime").value;

    return {
        venue_id: Number(venueSelect.value),

        purpose: document.getElementById("purpose").value.trim(),

        guest_count: Number(
            document.getElementById("guestCount").value
        ),

        start_time: startValue
            ? new Date(startValue).toISOString()
            : "",

        end_time: endValue
            ? new Date(endValue).toISOString()
            : ""
    };
}

// -------------------------------------------------
// VALIDATE FORM
// -------------------------------------------------

function validateForm() {

    const data = getFormData();

    if (!data.venue_id) {
        throw new Error("Please select a venue.");
    }

    if (!data.purpose) {
        throw new Error("Please enter the purpose of hire.");
    }

    if (data.purpose.length < 3) {
        throw new Error("Purpose must contain at least 3 characters.");
    }

    if (!Number.isInteger(data.guest_count) ||
        data.guest_count <= 0 ||
        data.guest_count > 10000) {

        throw new Error(
            "Guest count must be between 1 and 10000."
        );
    }

    const selectedOption = venueSelect.selectedOptions[0];

    const capacity = Number(selectedOption.dataset.capacity);

    if (data.guest_count > capacity) {
        throw new Error(
            `Guest count exceeds the selected venue capacity of ${capacity}.`
        );
    }

    if (!data.start_time || !data.end_time) {
        throw new Error("Please select start and end times.");
    }

    if (new Date(data.end_time) <= new Date(data.start_time)) {
        throw new Error("End time must be after start time.");
    }

    return data;
}

// -------------------------------------------------
// DISPLAY RESULT
// -------------------------------------------------

function displayResult(data) {

    resultCard.classList.remove("d-none");
    resultContent.replaceChildren();

    const performative = data.performative || "UNKNOWN";

    let status = data.status || "Not confirmed";

    if (performative === "AGREE" && data.available === true) {
        status = "AVAILABLE";
    }

    if (performative === "REFUSE") {
        status = "REJECTED";
    }

    if (performative === "PROPOSE") {
        status = "ALTERNATIVE PROPOSED";
    }

    const fields = [
        ["Response", performative],
        ["Status", status],
        ["Venue", data.venue_name || "Not specified"],
        ["Request ID", data.request_id ?? "Not created"],
        [
            "Quoted Price",
            data.quoted_price
                ? `${data.currency || "LKR"} ${data.quoted_price}`
                : "Not available"
        ],
        ["Capacity", data.capacity ?? data.venue_capacity ?? "Not specified"],
        ["Reason", data.reason || "No additional information"]
    ];

    fields.forEach(([label, value]) => {

        const p = document.createElement("p");

        const strong = document.createElement("strong");

        strong.textContent = `${label}: `;

        p.append(
            strong,
            document.createTextNode(String(value))
        );

        resultContent.appendChild(p);
    });

    // ALTERNATIVE VENUES

    if (
        Array.isArray(data.alternatives) &&
        data.alternatives.length > 0
    ) {

        const heading = document.createElement("h6");

        heading.className = "mt-3 fw-bold";
        heading.textContent = "Alternative Venues";

        resultContent.appendChild(heading);

        data.alternatives.forEach(item => {

            const card = document.createElement("div");

            card.className =
                "border rounded p-3 mb-2";

            const name = document.createElement("h6");

            name.textContent = item.venue_name;

            const details = document.createElement("p");

            details.className = "mb-0 text-muted";

            details.textContent =
                `${item.location} | Capacity: ${item.capacity} | ` +
                `LKR ${item.hourly_rate}/hour`;

            card.append(name, details);

            resultContent.appendChild(card);
        });
    }
}

// -------------------------------------------------
// CHECK AVAILABILITY
// -------------------------------------------------

availabilityButton.addEventListener("click", async () => {

    try {

        const data = validateForm();

        availabilityButton.disabled = true;
        availabilityButton.textContent = "Checking...";

        showMessage(
            "Checking venue availability...",
            "info"
        );

        const result = await apiRequest(
            `${API_URL}/availability`,
            {
                method: "POST",
                body: JSON.stringify(data)
            }
        );

        displayResult(result);

        if (result.performative === "AGREE") {

            showMessage(
                "Venue is available. You can now submit your hire request.",
                "success"
            );

        } else if (result.performative === "PROPOSE") {

            showMessage(
                result.reason || "Alternative venues are available.",
                "warning"
            );

        } else {

            showMessage(
                result.reason || "Venue is not available.",
                "danger"
            );
        }

    } catch (error) {

        showMessage(error.message, "danger");

    } finally {

        availabilityButton.disabled = false;
        availabilityButton.textContent = "Check Availability";
    }
});

// -------------------------------------------------
// SUBMIT PRIVATE HIRE REQUEST
// -------------------------------------------------

form.addEventListener("submit", async (event) => {

    event.preventDefault();

    try {

        const data = validateForm();

        submitButton.disabled = true;
        submitButton.textContent = "Submitting...";

        showMessage(
            "Submitting your private venue hire request...",
            "info"
        );

        const result = await apiRequest(
            `${API_URL}/request`,
            {
                method: "POST",
                body: JSON.stringify(data)
            }
        );

        displayResult(result);

        if (
            result.performative === "AGREE" &&
            result.status === "CONFIRMED"
        ) {

            showMessage(
                "Your venue hire request has been confirmed successfully!",
                "success"
            );

            form.reset();

        } else if (result.performative === "PROPOSE") {

            showMessage(
                result.reason || "Alternative venues have been proposed.",
                "warning"
            );

        } else {

            showMessage(
                result.reason || "Your request could not be confirmed.",
                "danger"
            );
        }

    } catch (error) {

        showMessage(error.message, "danger");

    } finally {

        submitButton.disabled = false;
        submitButton.textContent = "Submit Hire Request";
    }
});

// -------------------------------------------------
// INITIALIZE
// -------------------------------------------------

loadVenues();
loadHireHistory();
