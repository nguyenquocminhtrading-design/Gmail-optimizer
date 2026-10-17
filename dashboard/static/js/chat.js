(function () {
    const SESSION_KEY = "inbox-coworker-session";

    function getSessionId() {
        let id = localStorage.getItem(SESSION_KEY);
        if (!id) {
            id = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now());
            localStorage.setItem(SESSION_KEY, id);
        }
        return id;
    }

    function engineLabel(engine) {
        if (engine === "gemini") return "Gemini";
        if (engine === "qwen") return "Qwen 3.5 2B";
        return "Rules";
    }

    async function refreshLlmBadge() {
        const el = document.getElementById("llmBadge");
        if (!el) return;
        try {
            const res = await fetch("/api/llm");
            const data = await res.json();
            el.textContent = engineLabel(data.active);
        } catch (err) {
            el.textContent = "unknown";
        }
    }

    function appendBubble(role, text, engine) {
        const thread = document.getElementById("chatThread");
        if (!thread) return;
        const div = document.createElement("div");
        div.className = `bubble ${role}`;
        if (role === "assistant" && engine) {
            const meta = document.createElement("span");
            meta.className = "engine";
            meta.textContent = engineLabel(engine);
            div.appendChild(meta);
        }
        const body = document.createElement("div");
        body.className = "bubble-content";
        if (role === "assistant" && typeof window.marked !== "undefined") {
            try {
                body.innerHTML = window.marked.parse(text || "");
            } catch (e) {
                body.textContent = text;
            }
        } else {
            body.textContent = text;
        }
        div.appendChild(body);
        thread.appendChild(div);
        thread.scrollTop = thread.scrollHeight;
    }

    function renderCards(cards) {
        const side = document.getElementById("chatCards");
        if (!side) return;
        if (!cards || !cards.length) {
            side.innerHTML = `<div class="empty-note">No messages in this turn.</div>`;
            return;
        }
        side.innerHTML = cards.map((card) => {
            const labels = (card.proposed_labels || []).map((l) => `<span class="tag tag-career">${escapeHtml(l)}</span>`).join("");
            const initials = (card.sender_name || card.sender_email || '?')[0].toUpperCase();
            const dateStr = card.date_received
                ? new Date(card.date_received).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})
                : '';
            return `
                <article class="email-card">
                    <div class="email-header">
                        <div class="email-sender-wrap">
                            <div class="sender-avatar">${initials}</div>
                            <span class="email-sender">${escapeHtml(card.sender_name || card.sender_email || "")}</span>
                        </div>
                        <span class="email-date">${dateStr}</span>
                    </div>
                    <div class="email-subject">${escapeHtml(card.subject || "")}</div>
                    <div class="email-preview">${escapeHtml(card.preview || "")}</div>
                    <div class="tag-list">
                        <span class="tag tag-${(card.priority || "").toLowerCase()}">${escapeHtml(card.priority || "")}</span>
                        <span class="tag tag-career">${escapeHtml(card.category || "")}</span>
                        ${labels}
                    </div>
                    <div class="card-actions">
                        <button class="btn-accept" data-apply="${card.id}">✓ Apply labels</button>
                    </div>
                </article>
            `;
        }).join("");

        side.querySelectorAll("[data-apply]").forEach((btn) => {
            btn.addEventListener("click", () => sendChat("gắn nhãn thư này", true, [Number(btn.dataset.apply)]));
        });
    }

    function appendTypingIndicator() {
        const thread = document.getElementById("chatThread");
        if (!thread) return null;
        const div = document.createElement("div");
        div.className = "bubble assistant";
        div.id = "typingIndicator";
        div.innerHTML = `<div class="typing-dot"><span></span><span></span><span></span></div>`;
        thread.appendChild(div);
        thread.scrollTop = thread.scrollHeight;
        return div;
    }

    async function sendChat(message, confirm = false, emailIds = null) {
        if (!confirm) appendBubble("user", message);
        const typing = appendTypingIndicator();
        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message,
                    session_id: getSessionId(),
                    confirm,
                    email_ids: emailIds,
                }),
            });
            const data = await res.json();
            if (typing) typing.remove();
            if (!res.ok) {
                appendBubble("assistant", data.detail || "Chat failed.");
                return;
            }
            if (data.session_id) localStorage.setItem(SESSION_KEY, data.session_id);
            appendBubble("assistant", data.reply || "", data.engine);
            renderCards(data.cards || []);
            if (window.loadDashboardStats) loadDashboardStats();
            if (window.loadReviewQueue) loadReviewQueue();
            if (window.loadTodayImportant) loadTodayImportant();
        } catch (err) {
            if (typing) typing.remove();
            appendBubble("assistant", "Network error. Please try again.");
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        const form = document.getElementById("chatForm");
        const input = document.getElementById("chatInput");
        if (!form) return;

        refreshLlmBadge();
        appendBubble(
            "assistant",
            "Chào bạn! Mình là AI Assistant hỗ trợ phân loại Gmail. Bạn có thể hỏi mình về các thư quan trọng hoặc nhắn 'sync' để kéo email mới.",
            "heuristic"
        );

        form.addEventListener("submit", (ev) => {
            ev.preventDefault();
            const text = (input.value || "").trim();
            if (!text) return;
            input.value = "";
            sendChat(text).catch((err) => console.error(err));
        });

        document.querySelectorAll(".chip").forEach((chip) => {
            chip.addEventListener("click", () => sendChat(chip.dataset.prompt));
        });
    });

    window.refreshCoworkerAfterSync = function () {
        sendChat("Thư nào quan trọng?").catch((err) => console.error(err));
    };
})();
