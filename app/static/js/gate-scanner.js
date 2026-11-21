const token = sessionStorage.getItem("access_token") || localStorage.getItem("access_token");
const reader = document.getElementById("reader");
const startButton = document.getElementById("startScanner");
const stopButton = document.getElementById("stopScanner");
const validateButton = document.getElementById("validateTicket");
const manualQr = document.getElementById("manualQr");
const loading = document.getElementById("scannerLoading");
const result = document.getElementById("scanResult");
const confirmButton = document.getElementById("confirmCheckIn");
const permissionAlert = document.getElementById("cameraPermission");

let scanner = null;
let processing = false;
let pendingQr = null;

function gateLogout() {
    sessionStorage.clear();
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    window.location.href = "/ui/login";
}

document.getElementById("gateLogout")?.addEventListener("click", gateLogout);

if (!token) window.location.href = "/ui/login";

function showResult(status, message, data = null) {
    result.className = "gate-result d-none";
    result.classList.remove("d-none");

    const styles = {
        VALID: "gate-result-success",
        CHECK_IN_SUCCESS: "gate-result-success",
        ALREADY_CHECKED_IN: "gate-result-warning",
        INVALID_TICKET: "gate-result-danger",
        PAYMENT_NOT_COMPLETED: "gate-result-danger",
        EVENT_NOT_VALID: "gate-result-danger",
        TICKET_NOT_FOUND: "gate-result-danger"
    };
    result.classList.add(styles[status] || "gate-result-danger");
    result.innerHTML = `
        <span class="gate-result-label">${status.replaceAll("_", " ")}</span>
        <strong>${escapeGateScannerText(message)}</strong>
        ${data?.ticket_id ? `<small>Ticket ID: ${data.ticket_id}</small>` : ""}
        ${data?.event_title ? `<small>Event: ${escapeGateScannerText(data.event_title)}</small>` : ""}
        ${data?.attendee_name ? `<small>Attendee: ${escapeGateScannerText(data.attendee_name)}</small>` : ""}
    `;

    if (status === "VALID") {
        pendingQr = data?.qr_token || pendingQr;
        confirmButton.classList.remove("d-none");
    } else {
        pendingQr = null;
        confirmButton.classList.add("d-none");
    }
}

function escapeGateScannerText(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[character]);
}

async function validateToken(value) {
    if (processing) return;
    const trimmed = String(value || "").trim();
    if (!trimmed) {
        showResult("INVALID_TICKET", "Please enter a QR value or ticket ID.");
        return;
    }

    processing = true;
    loading.classList.remove("d-none");
    confirmButton.classList.add("d-none");

    try {
        const body = /^\d+$/.test(trimmed)
            ? { qr_token: trimmed }
            : { qr_token: trimmed };
        const response = await fetch("/gate/tickets/validate", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify(body)
        });
        const data = await response.json().catch(() => ({}));
        if (response.status === 401) gateLogout();
        if (response.status === 403) throw new Error("Gate Staff access is required.");
        if (!response.ok) throw new Error(data.detail || "Ticket validation failed.");

        pendingQr = trimmed;
        showResult(data.result || "INVALID_TICKET", data.message, {
            ...data,
            qr_token: trimmed
        });
    } catch (error) {
        showResult("INVALID_TICKET", error.message);
    } finally {
        loading.classList.add("d-none");
        processing = false;
    }
}

async function confirmCheckIn() {
    if (processing || !pendingQr) return;
    processing = true;
    loading.classList.remove("d-none");
    confirmButton.disabled = true;

    try {
        const body = /^\d+$/.test(pendingQr)
            ? { ticket_id: Number(pendingQr) }
            : { qr_token: pendingQr };
        const response = await fetch("/gate/tickets/check-in", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify(body)
        });
        const data = await response.json().catch(() => ({}));
        if (response.status === 401) gateLogout();

        if (!response.ok) {
            const detail = data.detail;
            const message = typeof detail === "object"
                ? detail.message
                : (detail || "Check-in could not be completed.");
            showResult(
                typeof detail === "object"
                    ? detail.result
                    : "INVALID_TICKET",
                message
            );
            return;
        }

        showResult("CHECK_IN_SUCCESS", "The ticket was checked in successfully.", {
            ticket_id: data.ticket_id,
            event_title: data.event_title,
            attendee_name: data.attendee_name
        });
        confirmButton.classList.add("d-none");
        pendingQr = null;
        manualQr.value = "";
    } catch (error) {
        showResult("INVALID_TICKET", error.message);
    } finally {
        loading.classList.add("d-none");
        confirmButton.disabled = false;
        processing = false;
    }
}

startButton.addEventListener("click", async () => {
    permissionAlert.classList.add("d-none");
    if (!window.Html5Qrcode) {
        permissionAlert.textContent = "Camera scanning is unavailable. Use manual entry.";
        permissionAlert.classList.remove("d-none");
        return;
    }
    if (scanner) return;

    scanner = new Html5Qrcode("reader");
    try {
        await scanner.start(
            { facingMode: "environment" },
            { fps: 10, qrbox: { width: 240, height: 240 } },
            async decodedText => {
                if (processing) return;
                await scanner.stop();
                scanner = null;
                startButton.disabled = false;
                stopButton.disabled = true;
                await validateToken(decodedText);
            },
            () => {}
        );
        startButton.disabled = true;
        stopButton.disabled = false;
    } catch (error) {
        scanner = null;
        startButton.disabled = false;
        stopButton.disabled = true;
        permissionAlert.textContent =
            "Camera permission or camera access failed. Allow camera access, try again, or use manual entry.";
        permissionAlert.classList.remove("d-none");
    }
});

stopButton.addEventListener("click", async () => {
    if (!scanner) return;
    await scanner.stop();
    scanner = null;
    startButton.disabled = false;
    stopButton.disabled = true;
});

validateButton.addEventListener("click", () => validateToken(manualQr.value));
manualQr.addEventListener("keydown", event => {
    if (event.key === "Enter") validateToken(manualQr.value);
});
confirmButton.addEventListener("click", confirmCheckIn);
