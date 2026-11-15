
const loading = document.getElementById("loading");
const eventContent = document.getElementById("eventContent");

const categorySelect = document.getElementById("ticketCategory");
const quantityInput = document.getElementById("ticketQuantity");

const bookingMessage = document.getElementById("bookingMessage");
const bookButton = document.getElementById("bookButton");
const joinWaitlistButton = document.getElementById("joinWaitlistButton");

const soldOutMessage = document.getElementById("soldOutMessage");

let currentEventId = null;
let categories = [];


// -----------------------------------------
// GET EVENT ID
// -----------------------------------------

function getEventId() {

    const parts = window.location.pathname.split("/");

    return Number(parts[parts.length - 1]);
}


// -----------------------------------------
// FORMAT DATE
// -----------------------------------------

function formatDate(value) {

    if (!value) return "Not available";

    return new Date(value).toLocaleString("en-US", {
        dateStyle: "medium",
        timeStyle: "short"
    });
}


// -----------------------------------------
// SHOW MESSAGE
// -----------------------------------------

function showBookingMessage(message, type = "danger") {

    bookingMessage.className = `alert alert-${type}`;

    bookingMessage.textContent = message;
}


// -----------------------------------------
// AUTHENTICATION
// -----------------------------------------

function getToken() {

    return sessionStorage.getItem("access_token");
}


function requireLogin() {

    const token = getToken();

    if (!token) {

        showBookingMessage(
            "Please login first. Redirecting to login page...",
            "warning"
        );

        setTimeout(() => {
            window.location.href = "/ui/login";
        }, 1200);

        return false;
    }

    return true;
}


// -----------------------------------------
// LOAD EVENT DETAILS
// -----------------------------------------

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


        // Event information

        document.getElementById("eventTitle").textContent =
            event.title;

        document.getElementById("eventCategory").textContent =
            event.category;

        document.getElementById("eventDescription").textContent =
            event.description || "No description available.";

        document.getElementById("venueName").textContent =
            event.venue_name;

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


// -----------------------------------------
// CHECK EVENT AVAILABILITY
// -----------------------------------------

function isEventSoldOut() {

    if (categories.length === 0) {
        return true;
    }

    return categories.every(category =>
        Number(category.available_quantity) <= 0
    );
}


// -----------------------------------------
// POPULATE TICKET CATEGORIES
// -----------------------------------------

function populateCategories() {

    categorySelect.innerHTML =
        '<option value="">Choose a ticket category</option>';


    categories.forEach(category => {

        const option = document.createElement("option");

        option.value = category.id;

        option.textContent =
            `${category.category_name} - LKR ${category.price} ` +
            `(${category.available_quantity} available)`;

        option.disabled =
            Number(category.available_quantity) <= 0;

        categorySelect.appendChild(option);

    });


    const soldOut = isEventSoldOut();

    soldOutMessage.classList.toggle("d-none", !soldOut);

    joinWaitlistButton.classList.toggle("d-none", !soldOut);

    bookButton.disabled = soldOut;

    bookButton.textContent = soldOut
        ? "Tickets Sold Out"
        : "Book Tickets";

    updatePrice();

}


// -----------------------------------------
// GET SELECTED CATEGORY
// -----------------------------------------

function getSelectedCategory() {

    return categories.find(
        category => String(category.id) === categorySelect.value
    );

}


// -----------------------------------------
// UPDATE PRICE
// -----------------------------------------

function updatePrice() {

    const category = getSelectedCategory();

    const quantity = Number(quantityInput.value);

    if (!category) {

        document.getElementById("ticketPrice").textContent =
            "LKR 0.00";

        document.getElementById("totalPrice").textContent =
            "LKR 0.00";

        return;
    }

    const price = Number(category.price);

    document.getElementById("ticketPrice").textContent =
        `LKR ${price.toFixed(2)}`;

    document.getElementById("totalPrice").textContent =
        `LKR ${(price * quantity).toFixed(2)}`;

}


// -----------------------------------------
// BOOK TICKETS
// -----------------------------------------

async function bookTickets() {

    if (!requireLogin()) return;

    const token = getToken();

    const category = getSelectedCategory();

    const quantity = Number(quantityInput.value);

    bookingMessage.classList.add("d-none");


    if (!category) {

        showBookingMessage(
            "Please select a ticket category."
        );

        return;
    }


    if (!Number.isInteger(quantity) || quantity < 1 || quantity > 10) {

        showBookingMessage(
            "Please select between 1 and 10 tickets."
        );

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

            const detail = result.detail;

            throw new Error(
                typeof detail === "string"
                    ? detail
                    : "Booking could not be completed."
            );
        }


        showBookingMessage(

            `Booking successful! Booking ID: ${result.booking_id}. ` +
            `Payment reference: ${result.payment_reference}. ` +
            `Total: LKR ${result.total_amount}.`,

            "success"

        );


        bookButton.textContent = "Booking Successful";


        await refreshCategories();


    } catch (error) {

        showBookingMessage(error.message);

        bookButton.disabled = false;

        bookButton.textContent = "Book Tickets";

    }

}


// -----------------------------------------
// JOIN WAITLIST
// -----------------------------------------

async function joinWaitlist() {

    if (!requireLogin()) return;

    const token = getToken();

    const quantity = Number(quantityInput.value);

    bookingMessage.classList.add("d-none");


    if (!Number.isInteger(quantity) || quantity < 1 || quantity > 10) {

        showBookingMessage(
            "Please select between 1 and 10 tickets."
        );

        return;
    }


    if (!isEventSoldOut()) {

        showBookingMessage(
            "Tickets are currently available. Please book your tickets instead.",
            "warning"
        );

        return;
    }


    joinWaitlistButton.disabled = true;

    joinWaitlistButton.textContent = "Joining Waitlist...";


    try {

        const response = await fetch("/waitlist/join", {

            method: "POST",

            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },

            body: JSON.stringify({

                event_id: currentEventId,

                quantity: quantity

            })

        });


        const result = await response.json();


        if (!response.ok) {

            const detail = result.detail;

            throw new Error(
                typeof detail === "string"
                    ? detail
                    : "Could not join the waitlist."
            );
        }


        showBookingMessage(

            `Successfully joined the waitlist! ` +
            `Waitlist ID: ${result.waitlist_id}. ` +
            `Quantity: ${result.quantity}. ` +
            `Status: ${result.status}.`,

            "success"

        );


        joinWaitlistButton.textContent = "Joined Waitlist";

        joinWaitlistButton.disabled = true;


    } catch (error) {

        showBookingMessage(error.message);

        joinWaitlistButton.disabled = false;

        joinWaitlistButton.textContent = "Join Waitlist";

    }

}


// -----------------------------------------
// REFRESH TICKET AVAILABILITY
// -----------------------------------------

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

        console.error(
            "Could not refresh ticket availability:",
            error
        );

    }

}


// -----------------------------------------
// EVENT LISTENERS
// -----------------------------------------

categorySelect.addEventListener("change", updatePrice);

quantityInput.addEventListener("input", updatePrice);

bookButton.addEventListener("click", bookTickets);

joinWaitlistButton.addEventListener("click", joinWaitlist);


// -----------------------------------------
// INITIALIZE
// -----------------------------------------

loadEventDetails();

refreshCategories();