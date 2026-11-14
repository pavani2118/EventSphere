const loading = document.getElementById("loading");
const eventContent = document.getElementById("eventContent");
const categorySelect = document.getElementById("ticketCategory");
const quantityInput = document.getElementById("ticketQuantity");
const bookingMessage = document.getElementById("bookingMessage");
const bookButton = document.getElementById("bookButton");

let currentEventId = null;
let categories = [];

function getEventId() {
    const parts = window.location.pathname.split("/");
    return Number(parts[parts.length - 1]);
}

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
    if (!value) return "Not available";

    return new Date(value).toLocaleString("en-US", {
        dateStyle: "medium",
        timeStyle: "short"
    });
}

function showBookingMessage(message, type = "danger") {
    bookingMessage.className = `alert alert-${type}`;
    bookingMessage.textContent = message;
}

async function loadEventDetails() {
    currentEventId = getEventId();

    if (!Number.isInteger(currentEventId) || currentEventId <= 0) {
        loading.textContent = "Invalid event ID.";
        return;
    }

    try {
        const [eventResponse, categoryResponse] = await Promise.all([
            fetch(`/events/${currentEventId}`),
            fetch(`/events/${currentEventId}/ticket-categories`)
        ]);

        if (!eventResponse.ok || !categoryResponse.ok) {
            throw new Error("Event details could not be loaded.");
        }

        const event = await eventResponse.json();
        const categoryData = await categoryResponse.json();

        document.getElementById("eventTitle").textContent = event.title;
        document.getElementById("eventCategory").textContent = event.category;
        document.getElementById("eventDescription").textContent =
            event.description || "No description available.";

        document.getElementById("venueName").textContent = event.venue_name;
        document.getElementById("venueLocation").textContent =
            event.venue_location;

        document.getElementById("startTime").textContent =
            formatDate(event.start_time);

        document.getElementById("endTime").textContent =
            formatDate(event.end_time);

        categories = categoryData.categories || [];

        populateCategories();

        loading.classList.add("d-none");
        eventContent.classList.remove("d-none");

    } catch (error) {
        loading.textContent = error.message;
    }
}

function populateCategories() {
    categorySelect.innerHTML =
        '<option value="">Choose a ticket category</option>';

    categories.forEach(category => {
        const option = document.createElement("option");

        option.value = category.id;
        option.textContent =
            `${category.category_name} - LKR ${category.price} ` +
            `(${category.available_quantity} available)`;

        option.disabled = Number(category.available_quantity) <= 0;

        categorySelect.appendChild(option);
    });

    updatePrice();
}

function getSelectedCategory() {
    return categories.find(
        category => String(category.id) === categorySelect.value
    );
}

function updatePrice() {
    const category = getSelectedCategory();
    const quantity = Number(quantityInput.value);

    if (!category) {
        document.getElementById("ticketPrice").textContent = "LKR 0.00";
        document.getElementById("totalPrice").textContent = "LKR 0.00";
        return;
    }

    const price = Number(category.price);

    document.getElementById("ticketPrice").textContent =
        `LKR ${price.toFixed(2)}`;

    document.getElementById("totalPrice").textContent =
        `LKR ${(price * quantity).toFixed(2)}`;
}

categorySelect.addEventListener("change", updatePrice);
quantityInput.addEventListener("input", updatePrice);

bookButton.addEventListener("click", async () => {
    const token = sessionStorage.getItem("access_token");
    const category = getSelectedCategory();
    const quantity = Number(quantityInput.value);

    bookingMessage.classList.add("d-none");

    if (!token) {
        showBookingMessage(
            "Please login before booking tickets. Redirecting to login...",
            "warning"
        );

        setTimeout(() => {
            window.location.href = "/ui/login";
        }, 1200);

        return;
    }

    if (!category) {
        showBookingMessage("Please select a ticket category.");
        return;
    }

    if (!Number.isInteger(quantity) || quantity < 1 || quantity > 10) {
        showBookingMessage("Please select between 1 and 10 tickets.");
        return;
    }

    if (quantity > Number(category.available_quantity)) {
        showBookingMessage(
            `Only ${category.available_quantity} tickets are available.`
        );
        return;
    }

    bookButton.disabled = true;
    bookButton.textContent = "Processing booking...";

    try {
        const response = await fetch("/bookings/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
                event_id: currentEventId,
                category_id: Number(category.id),
                quantity: quantity
            })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(
                result.detail || "Booking could not be completed."
            );
        }

        showBookingMessage(
            `Booking successful! Booking ID: ${result.booking_id}. ` +
            `Payment reference: ${result.payment_reference}. ` +
            `Total: LKR ${result.total_amount}.`,
            "success"
        );

        bookButton.textContent = "Booking Successful";

        // Refresh availability after successful booking.
        await refreshCategories();

    } catch (error) {
        showBookingMessage(error.message);
        bookButton.disabled = false;
        bookButton.textContent = "Book Tickets";
    }
});

async function refreshCategories() {
    try {
        const response = await fetch(
            `/events/${currentEventId}/ticket-categories`
        );

        if (!response.ok) return;

        const data = await response.json();
        categories = data.categories || [];

        populateCategories();

    } catch (error) {
        console.error("Could not refresh ticket availability:", error);
    }
}

loadEventDetails();