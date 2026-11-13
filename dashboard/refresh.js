document.addEventListener("DOMContentLoaded", () => {
    const historyList = document.getElementById("history-list");
    const reloadButton = document.getElementById("reload-refresh");
    const whatifForm = document.getElementById("whatif-form");
    const evaluateButton = document.getElementById("evaluate-button");
    const evaluationResult = document.getElementById("evaluation-result");

    // Safe text helper
    function setText(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value ?? "—";
        }
    }

    // Return the first field that exists on the object (backend field names can differ).
    function pick(obj, keys) {
        if (!obj) return undefined;
        for (const key of keys) {
            if (obj[key] !== undefined && obj[key] !== null) {
                return obj[key];
            }
        }
        return undefined;
    }

    function formatDate(value) {
        if (!value) return "Never";

        const date = new Date(value);

        return Number.isNaN(date.getTime())
            ? String(value)
            : date.toLocaleString();
    }

    function formatBudget(value) {
        if (value === undefined || value === null) return "Not available";
        const n = Number(value);
        return Number.isFinite(n)
            ? "$" + (n >= 0.01 ? n.toFixed(2) : n.toFixed(4))
            : String(value);
    }

    // The yellow note on the Refresh page: show the real last check instead of a fixed text.
    function updateNotice(status) {
        const notice = document.getElementById("refresh-notice");
        if (!notice) return;

        const checked = pick(status, ["last_checked"]);
        const decision = pick(status, ["last_decision"]);

        notice.textContent = checked
            ? `Last check: ${formatDate(checked)} · Decision: ${decision ?? "unknown"}`
            : "No refresh check has run yet. Use \"Run check now\" to compare the S3 documents with the last sync.";
    }

    // Load refresh status and history
    async function loadRefreshData() {
        if (reloadButton) {
            reloadButton.disabled = true;
            reloadButton.textContent = "Loading...";
        }

        try {
            const [statusResponse, historyResponse] = await Promise.all([
                fetch("/api/refresh/status"),
                fetch("/api/refresh/history?limit=20")
            ]);

            if (!statusResponse.ok) {
                throw new Error("Could not load refresh status.");
            }

            if (!historyResponse.ok) {
                throw new Error("Could not load refresh history.");
            }

            const status = await statusResponse.json();
            const historyData = await historyResponse.json();

            const enabled = pick(status, ["sync_enabled", "enabled", "refresh_enabled"]);
            const running = pick(status, ["job_running", "running", "is_running"]);
            const lastSync = pick(status, [
                "last_successful_sync",
                "last_sync",
                "last_sync_at",
                "last_refresh",
                "last_refresh_at",
                "last_run",
                "updated_at"
            ]);
            const budget = pick(status, ["budget", "remaining_budget", "budget_remaining"]);

            setText(
                "sync-enabled",
                enabled === undefined
                    ? "Not available"
                    : enabled
                        ? "Enabled"
                        : "Disabled"
            );

            setText(
                "job-running",
                running === undefined
                    ? "Not available"
                    : running
                        ? "Running"
                        : "Idle"
            );

            setText("last-sync", formatDate(lastSync));
            setText("budget", formatBudget(budget));
            updateNotice(status);

            if (historyList) {
                historyList.replaceChildren();

                const records = Array.isArray(historyData)
                    ? historyData
                    : historyData.history ?? historyData.records ?? historyData.items ?? [];

                if (!records.length) {
                    const empty = document.createElement("p");
                    empty.className = "empty-state";
                    empty.textContent = "No refresh history available yet.";
                    historyList.appendChild(empty);
                } else {
                    records.forEach((record) => {
                        const row = document.createElement("div");
                        row.className = "history-row";

                        const details = document.createElement("div");
                        details.className = "history-details";

                        const title = document.createElement("strong");
                        title.textContent =
                            pick(record, ["action", "event", "trigger", "type"]) ??
                            "Refresh run";

                        const time = document.createElement("span");
                        time.textContent = formatDate(
                            pick(record, ["timestamp", "created_at", "time", "run_at"])
                        );

                        details.append(title, time);

                        // Optional one-line reason, e.g. "1 of 4 files changed".
                        const reason = pick(record, ["reason", "details", "message"]);
                        if (reason) {
                            const note = document.createElement("span");
                            note.textContent = String(reason);
                            details.appendChild(note);
                        }

                        const result = document.createElement("span");
                        result.className = "history-status";
                        result.textContent =
                            pick(record, ["decision", "result", "status"]) ?? "Recorded";

                        row.append(details, result);
                        historyList.appendChild(row);
                    });
                }
            }
        } catch (error) {
            const notice = document.getElementById("refresh-notice");
            if (notice) {
                notice.textContent = error.message;
            }

            if (historyList) {
                historyList.replaceChildren();

                const message = document.createElement("p");
                message.className = "empty-state";
                message.textContent = error.message;
                historyList.appendChild(message);
            }

            if (window.showToast) {
                window.showToast(error.message);
            }
        } finally {
            if (reloadButton) {
                reloadButton.disabled = false;
                reloadButton.textContent = "↻ Reload";
            }
        }
    }

    if (reloadButton) {
        reloadButton.addEventListener("click", loadRefreshData);
    }

    // Run the real refresh check (compares S3 documents with the last sync).
    const runButton = document.getElementById("run-refresh");
    if (runButton) {
        runButton.addEventListener("click", async () => {
            runButton.disabled = true;
            runButton.textContent = "Checking...";

            try {
                const response = await fetch("/api/refresh/run", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({ force: false })
                });

                const data = await response.json().catch(() => ({}));

                if (!response.ok) {
                    throw new Error(
                        data.detail || data.message || "Refresh check failed."
                    );
                }

                if (window.showToast) {
                    window.showToast(`${data.decision ?? "Done"}: ${data.reason ?? ""}`);
                }

                await loadRefreshData();
            } catch (error) {
                if (window.showToast) {
                    window.showToast(error.message);
                }
            } finally {
                runButton.disabled = false;
                runButton.textContent = "▶ Run check now";
            }
        });
    }

    document.addEventListener("refresh-page-opened", loadRefreshData);

    // Keep slider labels synchronized with their values.
    [
        ["magnitude", "magnitude-out"],
        ["quality", "quality-out"],
        ["drop", "drop-out"]
    ].forEach(([sliderId, outputId]) => {
        const slider = document.getElementById(sliderId);
        const output = document.getElementById(outputId);

        if (slider && output) {
            const update = () => {
                output.textContent = Math.round(Number(slider.value) * 100) + "%";
            };

            slider.addEventListener("input", update);
            update();
        }
    });

    // Submit what-if evaluation
    if (whatifForm) {
        whatifForm.addEventListener("submit", async (event) => {
            event.preventDefault();

            if (evaluateButton) {
                evaluateButton.disabled = true;
                evaluateButton.textContent = "Evaluating...";
            }

            if (evaluationResult) {
                evaluationResult.textContent = "Evaluating scenario...";
                evaluationResult.classList.remove("hidden");
            }

            // Field names match RefreshRequest in main.py. "changed" and "urgent"
            // are <select> elements with "true"/"false" values.
            const payload = {
                document_changed: document.getElementById("changed")?.value === "true",
                urgent: document.getElementById("urgent")?.value === "true",
                change_magnitude: Number(document.getElementById("magnitude")?.value ?? 0),
                quality_score: Number(document.getElementById("quality")?.value ?? 0),
                quality_drop: Number(document.getElementById("drop")?.value ?? 0),
                hours_since_sync: Number(document.getElementById("hours")?.value ?? 0),
                estimated_sync_cost: Number(document.getElementById("cost")?.value ?? 0),
                budget_remaining: Number(document.getElementById("budget-input")?.value ?? 0)
            };

            try {
                const response = await fetch("/api/refresh/evaluate", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(payload)
                });

                const data = await response.json().catch(() => ({}));

                if (!response.ok) {
                    throw new Error(
                        data.detail || data.message || "Evaluation failed."
                    );
                }

                if (evaluationResult) {
                    evaluationResult.replaceChildren();

                    const heading = document.createElement("h3");
                    heading.textContent =
                        data.decision ?? data.recommendation ?? "Evaluation complete";

                    const explanation = document.createElement("p");
                    explanation.textContent =
                        data.reason ??
                        data.explanation ??
                        data.message ??
                        JSON.stringify(data, null, 2);

                    evaluationResult.append(heading, explanation);
                    evaluationResult.classList.remove("hidden");
                }
            } catch (error) {
                if (evaluationResult) {
                    evaluationResult.textContent = error.message;
                    evaluationResult.classList.remove("hidden");
                }

                if (window.showToast) {
                    window.showToast(error.message);
                }
            } finally {
                if (evaluateButton) {
                    evaluateButton.disabled = false;
                    evaluateButton.textContent = "Evaluate scenario";
                }
            }
        });
    }

    // Initial dashboard data
    loadRefreshData();
});