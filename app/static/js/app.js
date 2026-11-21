function showMessage(message, type = "danger") {
    const box = document.getElementById("message");

    if (!box) return;

    box.textContent = message;
    box.className = `alert alert-${type}`;
}

async function readResponse(response) {
    const data = await response.json();

    if (!response.ok) {
        const detail = data.detail;
        throw new Error(
            typeof detail === "string"
                ? detail
                : "Request failed. Please try again."
        );
    }

    return data;
}


// LOGIN
const loginForm = document.getElementById("loginForm");

if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const button = document.getElementById("loginButton");
        button.disabled = true;
        button.textContent = "Logging in...";

        try {
            const response = await fetch("/auth/login", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    email: document.getElementById("email").value.trim(),
                    password: document.getElementById("password").value
                })
            });

            const data = await readResponse(response);

            sessionStorage.setItem("access_token", data.access_token);
            sessionStorage.setItem("user", JSON.stringify(data.user));
            localStorage.setItem("access_token", data.access_token);
            localStorage.setItem("user", JSON.stringify(data.user));
            const next = new URLSearchParams(window.location.search).get("next");
            const safeNext = next && next.startsWith("/") && !next.startsWith("//")
                ? next
                : "/ui";

            window.location.href = safeNext;

        } catch (error) {
            showMessage(error.message);
        } finally {
            button.disabled = false;
            button.textContent = "Login";
        }
    });
}


// REGISTER
const registerForm = document.getElementById("registerForm");

if (registerForm) {
    registerForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const button = document.getElementById("registerButton");
        button.disabled = true;
        button.textContent = "Creating account...";

        try {
            const response = await fetch("/auth/register", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    full_name: document.getElementById("full_name").value.trim(),
                    email: document.getElementById("register_email").value.trim(),
                    password: document.getElementById("register_password").value
                })
            });

            await readResponse(response);

            showMessage(
                "Registration successful! You can now login.",
                "success"
            );

            registerForm.reset();

            setTimeout(() => {
                window.location.href = "/ui/login";
            }, 1200);

        } catch (error) {
            showMessage(error.message);
        } finally {
            button.disabled = false;
            button.textContent = "Create account";
        }
    });
}


// HOME PAGE AUTHENTICATION DISPLAY
const greeting = document.getElementById("userGreeting");

if (greeting) {
    let token = sessionStorage.getItem("access_token");
    let storedUser = sessionStorage.getItem("user");

    if (!token) {
        token = localStorage.getItem("access_token");
        storedUser = localStorage.getItem("user");

        if (token) {
            sessionStorage.setItem("access_token", token);
            if (storedUser) {
                sessionStorage.setItem("user", storedUser);
            }
        }
    }

    if (token && storedUser) {
        try {
            const user = JSON.parse(storedUser);

            greeting.textContent = `Hello, ${user.full_name}`;

            document.getElementById("loginLink").classList.add("d-none");
            document.getElementById("registerLink").classList.add("d-none");
            document.getElementById("logoutButton").classList.remove("d-none");
            document.getElementById("myTicketsLink").classList.remove("d-none");
            document.getElementById("myBookingsLink").classList.remove("d-none");
            document.getElementById("waitlistLink").classList.remove("d-none");
            document.getElementById("notificationsLink").classList.remove("d-none");

            const panel = document.getElementById("accountPanel");
            panel.textContent = `You are logged in as ${user.role}.`;
            panel.classList.remove("d-none");

            document.getElementById("exploreButton").href = "/docs";
            document.getElementById("exploreButton").textContent = "Explore API";

        } catch {
            sessionStorage.clear();
        }
    }
}


// LOGOUT
const logoutButton = document.getElementById("logoutButton");

if (logoutButton) {
    logoutButton.addEventListener("click", async () => {
        const token = sessionStorage.getItem("access_token");

        try {
            if (token) {
                await fetch("/auth/logout", {
                    method: "POST",
                    headers: {
                        "Authorization": `Bearer ${token}`
                    }
                });
            }


            // HOME PAGE PUBLISHED EVENTS
            const featuredEventsGrid = document.getElementById("featuredEventsGrid");
            const featuredEventsLoading = document.getElementById("featuredEventsLoading");
            const featuredEventsEmpty = document.getElementById("featuredEventsEmpty");

            function escapeHomeText(value) {
                return String(value ?? "").replace(/[&<>"']/g, character => ({
                    "&": "&amp;",
                    "<": "&lt;",
                    ">": "&gt;",
                    '"': "&quot;",
                    "'": "&#039;"
                })[character]);
            }

            function formatHomeEventDate(value) {
                if (!value) return "Date to be announced";

                return new Date(value).toLocaleString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit"
                });
            }

            async function loadFeaturedEvents() {
                if (!featuredEventsGrid) return;

                try {
                    const response = await fetch("/events/");
                    const data = await response.json();

                    if (!response.ok) {
                        throw new Error(data.detail || "Unable to load published events.");
                    }

                    const events = Array.isArray(data.events)
                        ? data.events.slice(0, 6)
                        : [];

                    featuredEventsLoading.classList.add("d-none");

                    if (events.length === 0) {
                        featuredEventsEmpty.classList.remove("d-none");
                        return;
                    }

                    featuredEventsGrid.classList.remove("d-none");
                    featuredEventsGrid.innerHTML = "";

                    events.forEach(event => {
                        const card = document.createElement("div");
                        card.className = "col-md-6 col-lg-4";

                        const availableImage =
                            event.image_path ||
                            event.image_url ||
                            event.image ||
                            null;

                        const visual = availableImage
                            ? `<img src="${escapeHomeText(availableImage)}"
                                    alt="${escapeHomeText(event.title || "Event")}"
                                    class="home-event-image"
                                    loading="lazy">`
                            : `<div class="home-event-placeholder" aria-hidden="true">
                                    <i class="bi bi-calendar2-event"></i>
                               </div>`;

                        card.innerHTML = `
                            <article class="home-event-card">
                                <div class="home-event-media">
                                    ${visual}
                                    <span class="home-event-category">
                                        ${escapeHomeText(event.category || "Event")}
                                    </span>
                                </div>
                                <div class="home-event-body">
                                    <h3>${escapeHomeText(event.title || "Untitled event")}</h3>
                                    <div class="home-event-meta">
                                        <span><i class="bi bi-geo-alt"></i>${escapeHomeText(event.venue_name || "Venue to be announced")}</span>
                                        <span><i class="bi bi-calendar3"></i>${escapeHomeText(formatHomeEventDate(event.start_time))}</span>
                                    </div>
                                    <a class="btn home-event-button"
                                       href="/ui/event/${encodeURIComponent(Number(event.id))}">
                                        View Details<i class="bi bi-arrow-right"></i>
                                    </a>
                                </div>
                            </article>
                        `;

                        featuredEventsGrid.appendChild(card);
                    });
                } catch (error) {
                    featuredEventsLoading.classList.add("d-none");
                    featuredEventsEmpty.classList.remove("d-none");
                    featuredEventsEmpty.querySelector("p").textContent =
                        error.message || "Published events could not be loaded.";
                }
            }

            loadFeaturedEvents();
        } finally {
            sessionStorage.removeItem("access_token");
            sessionStorage.removeItem("user");
            localStorage.removeItem("access_token");
            localStorage.removeItem("user");
            window.location.href = "/ui";
        }
    });
}