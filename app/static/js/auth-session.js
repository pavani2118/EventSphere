(function () {
    "use strict";

    const TOKEN_KEYS = ["access_token"];
    const USER_KEY = "user";

    function getToken() {
        for (const key of TOKEN_KEYS) {
            const sessionToken = (sessionStorage.getItem(key) || "").trim();
            if (sessionToken) return sessionToken;

            const localToken = (localStorage.getItem(key) || "").trim();
            if (localToken) {
                sessionStorage.setItem(key, localToken);
                const storedUser = localStorage.getItem(USER_KEY);
                if (storedUser) sessionStorage.setItem(USER_KEY, storedUser);
                return localToken;
            }
        }
        return "";
    }

    function getUser() {
        const sessionUser = sessionStorage.getItem(USER_KEY);
        if (sessionUser) {
            try {
                return JSON.parse(sessionUser);
            } catch (error) {
                sessionStorage.removeItem(USER_KEY);
            }
        }

        const localUser = localStorage.getItem(USER_KEY);
        if (localUser) {
            try {
                const user = JSON.parse(localUser);
                sessionStorage.setItem(USER_KEY, localUser);
                return user;
            } catch (error) {
                localStorage.removeItem(USER_KEY);
            }
        }
        return null;
    }

    function setSession(accessToken, user) {
        sessionStorage.setItem("access_token", accessToken);
        localStorage.setItem("access_token", accessToken);
        sessionStorage.setItem(USER_KEY, JSON.stringify(user));
        localStorage.setItem(USER_KEY, JSON.stringify(user));
    }

    function clearSession() {
        sessionStorage.removeItem("access_token");
        sessionStorage.removeItem(USER_KEY);
        localStorage.removeItem("access_token");
        localStorage.removeItem(USER_KEY);
    }

    function authHeaders(extraHeaders) {
        const token = getToken();
        return {
            ...(extraHeaders || {}),
            ...(token ? { "Authorization": `Bearer ${token}` } : {})
        };
    }

    function redirectToLogin() {
        clearSession();
        const next = `${window.location.pathname}${window.location.search}`;
        window.location.href =
            `/ui/login?next=${encodeURIComponent(next)}`;
    }

    async function handleResponse(response) {
        if (response.status === 401) {
            redirectToLogin();
            return { unauthorized: true };
        }

        if (response.status === 403) {
            return {
                forbidden: true,
                data: await response.json().catch(() => ({
                    detail: "You do not have permission to access this resource."
                }))
            };
        }

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            return {
                error: true,
                data,
                detail:
                    typeof data.detail === "string"
                        ? data.detail
                        : "The request could not be completed."
            };
        }
        return { data };
    }

    window.EventSphereAuth = {
        getToken,
        getUser,
        setSession,
        clearSession,
        authHeaders,
        redirectToLogin,
        handleResponse
    };
})();
