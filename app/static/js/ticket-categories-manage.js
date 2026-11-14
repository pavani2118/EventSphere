
const token = sessionStorage.getItem("access_token");
const eventId = window.location.pathname.split("/").filter(Boolean).pop();

const eventInfo = document.getElementById("eventInfo");
const categoryForm = document.getElementById("categoryForm");
const categoryRows = document.getElementById("categoryRows");
const addCategoryButton = document.getElementById("addCategoryButton");
const saveCategoriesButton = document.getElementById("saveCategoriesButton");
const message = document.getElementById("message");
const totalQuantity = document.getElementById("totalQuantity");

let venueCapacity = 0;
let existingQuantity = 0;
let existingCategories = [];

if (!token) {
    window.location.href = "/ui/login";
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

    const result = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(result.detail || "Something went wrong");
    }

    return result;
}

function showMessage(text, type = "success") {
    message.textContent = text;
    message.className = `alert alert-${type}`;
    message.classList.remove("d-none");
}

function hideMessage() {
    message.classList.add("d-none");
}

function addCategoryRow() {
    const row = document.createElement("div");
    row.className = "row g-2 align-items-end mb-3 category-row";

    row.innerHTML = `
        <div class="col-md-5">
            <label class="form-label">Category Name</label>
            <input type="text" class="form-control category-name"
                   placeholder="Example: VIP" required>
        </div>

        <div class="col-md-3">
            <label class="form-label">Price (LKR)</label>
            <input type="number" class="form-control category-price"
                   min="0" step="0.01" value="0" required>
        </div>

        <div class="col-md-2">
            <label class="form-label">Quantity</label>
            <input type="number" class="form-control category-quantity"
                   min="1" step="1" value="1" required>
        </div>

        <div class="col-md-2">
            <button type="button"
                    class="btn btn-outline-danger w-100 remove-category">
                Remove
            </button>
        </div>
    `;

    row.querySelectorAll("input").forEach(input => {
        input.addEventListener("input", updateTotalQuantity);
    });

    row.querySelector(".remove-category").addEventListener("click", () => {
        row.remove();
        updateTotalQuantity();
    });

    categoryRows.appendChild(row);
    updateTotalQuantity();
}

function updateTotalQuantity() {
    let newQuantity = 0;

    document.querySelectorAll(".category-quantity").forEach(input => {
        newQuantity += Math.max(0, Number(input.value) || 0);
    });

    const remaining = Math.max(0, venueCapacity - existingQuantity);

    totalQuantity.textContent =
        `Existing: ${existingQuantity} | New: ${newQuantity} | Remaining capacity: ${remaining}`;

    if (newQuantity > remaining) {
        totalQuantity.classList.add("text-danger");
        totalQuantity.classList.remove("text-success");
    } else {
        totalQuantity.classList.add("text-success");
        totalQuantity.classList.remove("text-danger");
    }
}

function displayExistingCategories(categories) {
    const container = document.getElementById("existingCategories");

    if (!container) return;

    container.innerHTML = "";

    if (!categories.length) {
        container.innerHTML =
            '<p class="text-muted">No ticket categories added yet.</p>';
        return;
    }

    const table = document.createElement("table");
    table.className = "table table-bordered table-hover";

    table.innerHTML = `
        <thead class="table-dark">
            <tr>
                <th>Category</th>
                <th>Price (LKR)</th>
                <th>Quantity</th>
                <th>Sold</th>
                <th>Available</th>
            </tr>
        </thead>
        <tbody></tbody>
    `;

    const tbody = table.querySelector("tbody");

    categories.forEach(category => {
        const tr = document.createElement("tr");

        const values = [
            category.category_name,
            Number(category.price).toFixed(2),
            category.quantity,
            category.sold_count ?? 0,
            category.available_quantity ?? category.quantity
        ];

        values.forEach(value => {
            const td = document.createElement("td");
            td.textContent = value;
            tr.appendChild(td);
        });

        tbody.appendChild(tr);
    });

    container.appendChild(table);
}

async function loadEventAndCategories() {
    try {
        hideMessage();

        const result = await apiRequest(
            `/events/manage/${eventId}/ticket-categories`
        );

        const event = result.event;
        existingCategories = result.categories || [];

        venueCapacity = Number(event.venue_capacity || 0);
        existingQuantity = existingCategories.reduce(
            (sum, category) => sum + Number(category.quantity || 0),
            0
        );

        document.getElementById("eventTitle").textContent = event.title;
        document.getElementById("eventStatus").textContent = event.status;
        document.getElementById("venueCapacity").textContent = venueCapacity;

        displayExistingCategories(existingCategories);
        updateTotalQuantity();

        if (event.status !== "DRAFT") {
            categoryForm.classList.add("d-none");
            showMessage(
                "This event is not a draft. Ticket categories can no longer be changed.",
                "warning"
            );
        } else {
            categoryForm.classList.remove("d-none");

            // Show one empty row when there are no unsaved rows.
            if (categoryRows.children.length === 0) {
                addCategoryRow();
            }
        }

    } catch (error) {
        showMessage(error.message, "danger");
    }
}

categoryForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    hideMessage();

    const rows = [...document.querySelectorAll(".category-row")];

    if (rows.length === 0) {
        showMessage("Please add at least one new ticket category.", "warning");
        return;
    }

    const categories = rows.map(row => ({
        category_name: row.querySelector(".category-name").value.trim(),
        price: Number(row.querySelector(".category-price").value),
        quantity: Number(row.querySelector(".category-quantity").value)
    }));

    if (categories.some(item => !item.category_name)) {
        showMessage("Please enter a name for every category.", "warning");
        return;
    }

    if (categories.some(item =>
        !Number.isFinite(item.price) || item.price < 0 ||
        !Number.isInteger(item.quantity) || item.quantity <= 0
    )) {
        showMessage(
            "Enter a valid price and a positive whole-number quantity.",
            "warning"
        );
        return;
    }

    const remaining = venueCapacity - existingQuantity;
    const newQuantity = categories.reduce(
        (sum, item) => sum + item.quantity, 0
    );

    if (newQuantity > remaining) {
        showMessage(
            `You can only add ${remaining} more tickets. Venue capacity is ${venueCapacity}.`,
            "danger"
        );
        return;
    }

    saveCategoriesButton.disabled = true;
    saveCategoriesButton.textContent = "Saving...";

    try {
        const result = await apiRequest(
            `/events/${eventId}/ticket-categories`,
            {
                method: "POST",
                body: JSON.stringify({ categories })
            }
        );

        categoryRows.innerHTML = "";

        showMessage(
            `${result.added_count} new ticket category/categories added successfully.`,
            "success"
        );

        await loadEventAndCategories();

    } catch (error) {
        showMessage(error.message, "danger");
    } finally {
        saveCategoriesButton.disabled = false;
        saveCategoriesButton.textContent = "Save New Categories";
    }
});

addCategoryButton.addEventListener("click", addCategoryRow);

function logout() {
    sessionStorage.clear();
    window.location.href = "/ui/login";
}

loadEventAndCategories();
