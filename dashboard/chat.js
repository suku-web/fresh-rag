document.addEventListener("DOMContentLoaded", () => {
    const chatForm = document.getElementById("chat-form");
    const questionInput = document.getElementById("question");
    const messagesContainer = document.getElementById("messages");
    const sendButton = document.getElementById("send-button");
    const chatIntro = document.getElementById("chat-intro");

    if (!chatForm || !questionInput || !messagesContainer || !sendButton) {
        console.error("Chat elements are missing from index.html.");
        return;
    }

    // Turn a source (string or object like {"document": "..."}) into a short file name.
    function sourceName(source) {
        if (typeof source === "string") {
            return source.split(/[\\/]/).pop();
        }
        if (source && typeof source === "object") {
            const raw =
                source.document ??
                source.source ??
                source.file ??
                source.filename ??
                source.name ??
                source.title;
            if (typeof raw === "string") {
                return raw.split(/[\\/]/).pop();
            }
            return JSON.stringify(source);
        }
        return String(source);
    }

    function formatNumber(value) {
        const n = Number(value);
        return Number.isFinite(n) ? n.toFixed(2).replace(/\.?0+$/, "") || "0" : null;
    }

    function formatCost(value) {
        const n = Number(value);
        if (!Number.isFinite(n)) return null;
        if (n === 0) return "$0";
        return "$" + n.toFixed(5).replace(/0+$/, "").replace(/\.$/, "");
    }

    // Small strip under the answer: decision, relevance, confidence, quality, cost, provider.
    function buildAdaptiveBar(meta) {
        if (!meta || !meta.decision) return null;

        const bar = document.createElement("div");
        bar.className = "adaptive-bar";
        bar.style.cssText =
            "display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;" +
            "margin-top:10px;font-size:12px;opacity:0.85;";

        const decision = String(meta.decision).toUpperCase();
        const badge = document.createElement("span");
        badge.className = "adaptive-decision";
        badge.textContent = decision;
        const color =
            decision === "ANSWER" ? "#1a7f37" :
            decision === "ABSTAIN" ? "#b54708" : "#555";
        badge.style.cssText =
            `background:${color};color:#fff;padding:2px 8px;border-radius:999px;` +
            "font-weight:600;letter-spacing:0.3px;";
        bar.appendChild(badge);

        const parts = [];
        const rel = formatNumber(meta.relevance_score);
        const conf = formatNumber(meta.confidence_score);
        const cost = formatCost(meta.estimated_cost);

        if (rel !== null) parts.push(`Relevance ${rel}`);
        if (conf !== null) parts.push(`Confidence ${conf}`);
        if (meta.quality_level) parts.push(`Quality ${meta.quality_level}`);
        if (cost !== null) parts.push(`Est. cost ${cost}`);
        if (meta.provider) parts.push(String(meta.provider));
        if (meta.mode) parts.push(`Mode ${meta.mode}`);

        parts.forEach((text) => {
            const span = document.createElement("span");
            span.textContent = text;
            bar.appendChild(span);
        });

        return bar;
    }

    function addMessage(role, text, sources = [], meta = null) {
        const message = document.createElement("div");
        message.className = `message ${role}`;

        const label = document.createElement("div");
        label.className = "message-label";
        label.textContent = role === "user" ? "You" : "AI Assistant";

        const content = document.createElement("div");
        content.className = "message-content";
        content.textContent = text || "No response was returned.";

        message.append(label, content);

        const adaptiveBar = buildAdaptiveBar(meta);
        if (adaptiveBar) {
            message.appendChild(adaptiveBar);
        }

        if (Array.isArray(sources) && sources.length > 0) {
            // Show each document only once.
            const names = [...new Set(sources.map(sourceName))];

            const sourceBox = document.createElement("div");
            sourceBox.className = "sources";

            const heading = document.createElement("strong");
            heading.textContent = "Sources";
            sourceBox.appendChild(heading);

            const list = document.createElement("ul");

            names.forEach((name) => {
                const item = document.createElement("li");
                item.textContent = name;
                list.appendChild(item);
            });

            sourceBox.appendChild(list);
            message.appendChild(sourceBox);
        }

        messagesContainer.appendChild(message);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        return message;
    }

    async function sendQuestion(question) {
        const cleanedQuestion = question.trim();

        if (!cleanedQuestion) {
            questionInput.focus();
            return;
        }

        addMessage("user", cleanedQuestion);

        questionInput.value = "";
        questionInput.disabled = true;
        sendButton.disabled = true;
        sendButton.textContent = "Thinking...";

        if (chatIntro) {
            chatIntro.classList.add("hidden");
        }

        const loadingMessage = addMessage("assistant", "Preparing your answer...");

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    question: cleanedQuestion
                })
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(
                    data.detail || data.message || `Request failed (${response.status})`
                );
            }

            const answer =
                data.answer ??
                data.response ??
                data.message ??
                "The API returned no answer.";

            const sources = data.sources ?? data.context ?? [];

            loadingMessage.remove();
            addMessage("assistant", String(answer), sources, data);

        } catch (error) {
            loadingMessage.remove();

            addMessage(
                "assistant",
                `Sorry, I couldn't get an answer. ${error.message}\n\nCheck that the backend is running and that /api/chat is available.`
            );
        } finally {
            questionInput.disabled = false;
            sendButton.disabled = false;
            sendButton.textContent = "Send";
            questionInput.focus();
        }
    }

    chatForm.addEventListener("submit", (event) => {
        event.preventDefault();
        sendQuestion(questionInput.value);
    });

    // Allow suggestion buttons to fill and send a question.
    document.querySelectorAll(".suggestion[data-question]").forEach((button) => {
        button.addEventListener("click", () => {
            sendQuestion(button.dataset.question || "");
        });
    });

    // Start a fresh chat.
    document.addEventListener("new-chat-requested", () => {
        messagesContainer.replaceChildren();

        if (chatIntro) {
            chatIntro.classList.remove("hidden");
        }

        questionInput.value = "";
        questionInput.disabled = false;
        sendButton.disabled = false;
        sendButton.textContent = "Send";
        questionInput.focus();
    });
});