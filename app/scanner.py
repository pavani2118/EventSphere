from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(
    tags=["Gate Scanner"]
)


@router.get("/scanner", response_class=HTMLResponse)
def scanner_page():

    return """
    <!DOCTYPE html>
    <html lang="en">

    <head>
        <meta charset="UTF-8">

        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">

        <title>EventSphere Gate Scanner</title>

        <link
          href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
          rel="stylesheet">

        <link
          href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css"
          rel="stylesheet">

        <link
          rel="stylesheet"
          href="/static/css/style.css?v=7">

        <script src="https://unpkg.com/html5-qrcode"></script>
    </head>

    <body class="bg-light">

        <nav class="navbar navbar-dark bg-dark">
            <div class="container">
                <a class="navbar-brand" href="/ui">EventSphere Staff</a>
                <a class="btn btn-outline-light btn-sm" href="/ui">
                    <i class="bi bi-arrow-left"></i> Back to Dashboard
                </a>
            </div>
        </nav>

        <div class="container py-4">

            <div class="card shadow-sm mx-auto"
                 style="max-width: 600px;">

                <div class="card-body">

                    <h2 class="text-center mb-3">
                        EventSphere Gate Scanner
                    </h2>

                    <p class="text-muted text-center">
                        Scan attendee QR tickets or enter a token manually.
                    </p>

                    <label class="form-label">
                        Gate Staff Access Token
                    </label>

                    <input
                        type="password"
                        id="accessToken"
                        class="form-control mb-3"
                        placeholder="Paste access token">

                    <div id="reader"
                         class="mb-3">
                    </div>

                    <button
                        class="btn btn-primary w-100 mb-3"
                        onclick="startScanner()">

                        Start QR Scanner

                    </button>

                    <hr>

                    <label class="form-label">
                        Manual QR Token
                    </label>

                    <input
                        type="text"
                        id="manualToken"
                        class="form-control mb-3"
                        placeholder="Enter QR token">

                    <button
                        class="btn btn-success w-100"
                        onclick="submitToken(
                            document.getElementById('manualToken').value
                        )">

                        Validate Ticket

                    </button>

                    <div id="result"
                         class="mt-3">
                    </div>

                </div>

            </div>

        </div>

        <script>

            let scanner = null;
            let processing = false;

            async function submitToken(token) {

                if (!token) {
                    showResult(
                        "Please provide a QR token.",
                        false
                    );
                    return;
                }

                const accessToken =
                    document.getElementById("accessToken").value;

                if (!accessToken) {
                    showResult(
                        "Please enter your Gate Staff access token.",
                        false
                    );
                    return;
                }

                try {

                    const response = await fetch(
                        "/tickets/check-in",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type": "application/json",
                                "Authorization": "Bearer " + accessToken
                            },

                            body: JSON.stringify({
                                qr_token: token
                            })
                        }
                    );

                    const result = await response.json();

                    if (!response.ok) {
                        showResult(
                            result.detail || "Ticket validation failed.",
                            false
                        );
                        return;
                    }

                    showResult(
                        "SUCCESS: " +
                        result.event_title +
                        " - " +
                        result.category,
                        true
                    );

                    document.getElementById(
                        "manualToken"
                    ).value = "";

                } catch (error) {

                    showResult(
                        "Unable to connect to EventSphere server.",
                        false
                    );

                }
            }


            function showResult(message, success) {

                const result =
                    document.getElementById("result");

                result.className =
                    success
                    ? "alert alert-success mt-3"
                    : "alert alert-danger mt-3";

                result.textContent = message;
            }


            function startScanner() {

                if (scanner !== null) {
                    return;
                }

                scanner = new Html5Qrcode("reader");

                scanner.start(
                    { facingMode: "environment" },

                    {
                        fps: 10,
                        qrbox: {
                            width: 250,
                            height: 250
                        }
                    },

                    async (decodedText) => {

                        if (processing) {
                            return;
                        }

                        processing = true;

                        await scanner.stop();

                        scanner = null;

                        await submitToken(decodedText);

                        processing = false;
                    },

                    (errorMessage) => {
                        // Ignore normal scanning errors.
                    }

                ).catch((error) => {

                    scanner = null;

                    showResult(
                        "Camera could not start. Use manual entry.",
                        false
                    );

                });

            }

        </script>

    </body>
    </html>
    """