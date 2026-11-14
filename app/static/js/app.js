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

            window.location.href = "/ui";

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
    const token = sessionStorage.getItem("access_token");
    const storedUser = sessionStorage.getItem("user");

    if (token && storedUser) {
        try {
            const user = JSON.parse(storedUser);

            greeting.textContent = `Hello, ${user.full_name}`;

            document.getElementById("loginLink").classList.add("d-none");
            document.getElementById("registerLink").classList.add("d-none");
            document.getElementById("logoutButton").classList.remove("d-none");

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
        } finally {
            sessionStorage.removeItem("access_token");
            sessionStorage.removeItem("user");
            window.location.href = "/ui";
        }
    });
}