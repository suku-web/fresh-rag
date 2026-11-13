
const API_BASE = "";

document.addEventListener("DOMContentLoaded", () => {
    // Sidebar navigation
    const navItems = document.querySelectorAll(".nav-item");
    const pages = document.querySelectorAll(".page");
    const pageTitle = document.getElementById("page-title");

    const titles = {
        chat: "AI Chat",
        refresh: "Refresh Monitor",
        whatif: "What-if Analysis"
    };

    function showPage(pageName) {
        pages.forEach((page) => {
            page.classList.toggle("active", page.id === `page-${pageName}`);
        });

        navItems.forEach((item) => {
            item.classList.toggle("active", item.dataset.page === pageName);
        });

        if (pageTitle) {
            pageTitle.textContent = titles[pageName] || "Dashboard";
        }

        if (pageName === "refresh") {
            document.dispatchEvent(new Event("refresh-page-opened"));
        }
    }

    navItems.forEach((item) => {
        item.addEventListener("click", () => {
            showPage(item.dataset.page);
        });
    });

    // New chat
    const newChatButton = document.getElementById("new-chat");

    if (newChatButton) {
        newChatButton.addEventListener("click", () => {
            showPage("chat");
            document.dispatchEvent(new Event("new-chat-requested"));
        });
    }

    // Dark/light theme
    const themeToggle = document.getElementById("theme-toggle");

    if (themeToggle) {
        themeToggle.addEventListener("click", () => {
            const isLight = document.body.classList.toggle("light");
            themeToggle.textContent = isLight ? "☾ Dark mode" : "☀ Light mode";
        });
    }

    // Toast notification helper
    window.showToast = function (message, duration = 3000) {
        const toast = document.getElementById("toast");

        if (!toast) return;

        toast.textContent = message;
        toast.classList.add("show");

        clearTimeout(window.toastTimer);
        window.toastTimer = setTimeout(() => {
            toast.classList.remove("show");
        }, duration);
    };

    // Backend connection status
    async function checkConnection() {
        const dot = document.getElementById("status-dot");
        const text = document.getElementById("connection-text");

        try {
            const response = await fetch(`${API_BASE}/api/health`);
            if (!response.ok) throw new Error("API unavailable");

            const data = await response.json();

            if (dot) {
                dot.classList.add("online");
                dot.classList.remove("offline");
            }

            if (text) {
                text.textContent =
                    data.status === "healthy" ? "API connected" : "API available";
            }
        } catch (error) {
            if (dot) {
                dot.classList.remove("online");
                dot.classList.add("offline");
            }

            if (text) {
                text.textContent = "API disconnected";
            }
        }
    }

    checkConnection();
});
