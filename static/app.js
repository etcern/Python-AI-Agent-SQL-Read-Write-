/* --- QueryMaster - Frontend Logic ---
   Pure JS, no framework. Communicates with the FastAPI backend via fetch.
   State lives in memory; user preferences persist to localStorage.
   Ref: https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API */


/* --- Constants --- */

const THEME_MAP = {
    "codingstars-dark": "",
    "vscode-dark":      "theme-vscode-dark",
    "midnight":         "theme-midnight",
};

const DEFAULT_CTX = 8192;


/* --- State --- */

let activeChatId = null;
let chats = [];
let agents = [];
let renamingId = null;
let internetEnabled = localStorage.getItem("qm_internet") !== "false";
let confirmationMode = localStorage.getItem("qm_confirm") === "true";
let thinkingEnabled = localStorage.getItem("qm_thinking") === "true";
let activeProfile = localStorage.getItem("qm_profile") || "auto";
let isRecording = false;
let speechRecognition = null;
let lastSentMessage = "";
let modelThinkingSupport = {};


/* --- Settings (persisted to localStorage) ---
   Ref: https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage */

function loadSettings() {
    return {
        theme:         localStorage.getItem("qm_theme") || "codingstars-dark",
        font:          localStorage.getItem("qm_font")  || "Roboto",
        contextWindow: parseInt(localStorage.getItem("qm_ctx") || DEFAULT_CTX, 10),
    };
}

function saveSettings(s) {
    localStorage.setItem("qm_theme", s.theme);
    localStorage.setItem("qm_font",  s.font);
    localStorage.setItem("qm_ctx",   s.contextWindow);
}


/* --- Apply settings to the DOM --- */

function applyTheme(themeKey) {
    document.body.className = document.body.className
        .replace(/theme-\S+/g, "").trim();
    const cls = THEME_MAP[themeKey];
    if (cls) document.body.classList.add(cls);
    /* -- Keep sidebar-collapsed class intact -- */
    if (document.body.dataset.sidebarState === "collapsed") {
        document.body.classList.add("sidebar-collapsed");
    }
}

function applyFont(fontName) {
    document.documentElement.style.setProperty(
        "--user-font", `'${fontName}', sans-serif`
    );
}


/* --- API helpers ---
   Ref: https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch */

async function api(path, opts = {}) {
    const res = await fetch(`/api${path}`, {
        headers: { "Content-Type": "application/json", ...opts.headers },
        ...opts,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
}


/* --- DOM references --- */

const $chatList       = document.getElementById("chat-list");
const $sidebarActions = document.getElementById("sidebar-actions");
const $welcome        = document.getElementById("welcome");
const $messages       = document.getElementById("messages");
const $input          = document.getElementById("input");
const $agentLabel     = document.getElementById("agent-label");
const $agentDropdown  = document.getElementById("agent-dropdown");
const $agentList      = document.getElementById("agent-list");
const $modelSelect    = document.getElementById("model-select");
const $settingsDD     = document.getElementById("settings-dropdown");
const $themeSelect    = document.getElementById("theme-select");
const $fontSelect     = document.getElementById("font-select");
const $ctxSelect      = document.getElementById("ctx-select");
const $showcase       = document.getElementById("showcase-info");
const $filesDD        = document.getElementById("files-dropdown");
const $fileList       = document.getElementById("file-list");
const $fileInput      = document.getElementById("file-input");
const $uploadBadge    = document.getElementById("upload-badge");


/* --- Markdown rendering ---
   Ref: https://marked.js.org/
   Ref: https://github.com/cure53/DOMPurify
   Ref: https://highlightjs.org/ */

marked.setOptions({
    breaks: true,
    gfm: true,
    highlight: function (code, lang) {
        if (lang && hljs.getLanguage(lang)) {
            return hljs.highlight(code, { language: lang }).value;
        }
        return hljs.highlightAuto(code).value;
    },
});

function renderMarkdown(text) {
    const raw = marked.parse(text || "");
    return DOMPurify.sanitize(raw);
}


/* --- Sidebar: render chat list --- */

function renderChatList() {
    $chatList.innerHTML = "";
    /* -- Show newest at top (API returns newest first) -- */
    for (const c of chats) {
        const btn = document.createElement("button");
        btn.className = "chat-item" + (c.id === activeChatId ? " active" : "");
        btn.textContent = c.title || "New chat";
        btn.title = c.title || "New chat";
        btn.addEventListener("click", () => switchChat(c.id));
        $chatList.appendChild(btn);
    }
    renderSidebarActions();
}


/* --- Sidebar: bottom actions (rename + delete) --- */

function renderSidebarActions() {
    $sidebarActions.innerHTML = "";
    if (!activeChatId) return;

    if (renamingId === activeChatId) {
        /* -- Rename mode: text input + save/cancel -- */
        const chat = chats.find(c => c.id === activeChatId);
        const inp = document.createElement("input");
        inp.className = "rename-input";
        inp.value = chat ? chat.title : "";
        inp.addEventListener("keydown", (e) => {
            if (e.key === "Enter") doRename(inp.value);
            if (e.key === "Escape") cancelRename();
        });

        const row = document.createElement("div");
        row.className = "rename-row";

        const saveBtn = document.createElement("button");
        saveBtn.className = "rename-save";
        saveBtn.textContent = "Save";
        saveBtn.addEventListener("click", () => doRename(inp.value));

        const cancelBtn = document.createElement("button");
        cancelBtn.className = "rename-cancel";
        cancelBtn.textContent = "Cancel";
        cancelBtn.addEventListener("click", cancelRename);

        row.appendChild(saveBtn);
        row.appendChild(cancelBtn);
        $sidebarActions.appendChild(inp);
        $sidebarActions.appendChild(row);

        setTimeout(() => { inp.focus(); inp.select(); }, 50);
    } else {
        const renameBtn = document.createElement("button");
        renameBtn.textContent = "Rename";
        renameBtn.addEventListener("click", () => {
            renamingId = activeChatId;
            renderSidebarActions();
        });

        const deleteBtn = document.createElement("button");
        deleteBtn.textContent = "Delete";
        deleteBtn.addEventListener("click", deleteActiveChat);

        $sidebarActions.appendChild(renameBtn);
        $sidebarActions.appendChild(deleteBtn);
    }
}

async function doRename(newTitle) {
    if (!newTitle.trim()) return;
    try {
        await api(`/chats/${activeChatId}`, {
            method: "PATCH",
            body: JSON.stringify({ title: newTitle.trim() }),
        });
        const chat = chats.find(c => c.id === activeChatId);
        if (chat) chat.title = newTitle.trim();
    } catch (e) {
        console.error("Rename failed:", e);
    }
    renamingId = null;
    renderChatList();
}

function cancelRename() {
    renamingId = null;
    renderSidebarActions();
}

async function deleteActiveChat() {
    if (!activeChatId) return;
    try {
        await api(`/chats/${activeChatId}`, { method: "DELETE" });
        chats = chats.filter(c => c.id !== activeChatId);
        if (chats.length > 0) {
            await switchChat(chats[0].id);
        } else {
            await createNewChat();
        }
    } catch (e) {
        console.error("Delete failed:", e);
    }
}


/* --- Chat switching --- */

async function switchChat(chatId) {
    activeChatId = chatId;
    renamingId = null;
    renderChatList();
    await loadMessages(chatId);
    updateAgentLabel();

    /* -- On mobile, close sidebar after switching -- */
    if (window.innerWidth <= 768) {
        document.body.classList.add("sidebar-collapsed");
        document.body.dataset.sidebarState = "collapsed";
    }
}


/* --- Create new chat --- */

async function createNewChat() {
    try {
        const chat = await api("/chats", {
            method: "POST",
            body: JSON.stringify({ agent: "sql" }),
        });
        chats.unshift(chat);
        await switchChat(chat.id);
    } catch (e) {
        console.error("Failed to create chat:", e);
    }
}


/* --- Load and render messages --- */

async function loadMessages(chatId) {
    try {
        const msgs = await api(`/chats/${chatId}/messages`);
        renderMessages(msgs);
    } catch (e) {
        console.error("Failed to load messages:", e);
        renderMessages([]);
    }
}

function renderMessages(msgs) {
    $messages.innerHTML = "";
    if (msgs.length === 0) {
        $welcome.classList.remove("hidden");
        return;
    }
    $welcome.classList.add("hidden");

    for (const m of msgs) {
        appendMessage(m.role, m.content);
    }
    scrollToBottom();
}

function appendMessage(role, content, toolEvents = []) {
    $welcome.classList.add("hidden");

    const row = document.createElement("div");
    row.className = `msg ${role}`;

    /* -- Avatar -- */
    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    const icon = document.createElement("span");
    icon.className = "material-symbols-rounded";
    icon.textContent = role === "user" ? "person" : "smart_toy";
    avatar.appendChild(icon);

    /* -- Content -- */
    const body = document.createElement("div");
    body.className = "msg-content";

    if (role === "assistant") {
        /* -- Thought process panel (before message content) -- */
        if (toolEvents.length > 0) {
            body.appendChild(renderThoughtProcess(toolEvents));
        }

        if (content.startsWith("Error:")) {
            body.appendChild(buildErrorWithRetry(content));
        } else {
            const contentDiv = document.createElement("div");
            contentDiv.innerHTML = renderMarkdown(content);
            body.appendChild(contentDiv);
            addCopyButtons(contentDiv);
        }
    } else {
        body.textContent = content;
    }

    row.appendChild(avatar);
    row.appendChild(body);
    $messages.appendChild(row);
}


/* --- Thought process panel ---
   Collapsible section showing each tool call with severity badge.
   Ref: https://developer.mozilla.org/en-US/docs/Web/API/Element/classList */

function renderThoughtProcess(toolEvents) {
    const container = document.createElement("div");
    container.className = "thought-process";

    /* -- Toggle header -- */
    const toggle = document.createElement("button");
    toggle.className = "thought-toggle";
    const count = toolEvents.length;
    toggle.innerHTML = `
        <span class="material-symbols-rounded">psychology</span>
        <span>Thought Process (${count} step${count > 1 ? "s" : ""})</span>
        <span class="material-symbols-rounded thought-arrow">expand_more</span>
    `;

    /* -- Steps list -- */
    const steps = document.createElement("div");
    steps.className = "thought-steps hidden";

    const badges = { low: "\u{1F7E2}", medium: "\u{1F7E1}", high: "\u{1F534}" };

    for (const evt of toolEvents) {
        const isThinking = evt.tool === "_thinking";
        const step = document.createElement("div");
        step.className = isThinking
            ? "thought-step thinking-step"
            : `thought-step severity-${evt.severity || "low"}`;

        if (isThinking) {
            /* -- Thinking step: show reasoning content with brain icon -- */
            let html = `<div class="step-header">
                <span class="severity-badge">\u{1F9E0}</span>
                <span class="step-tool">Thinking</span>
            </div>`;
            if (evt.reasoning) {
                html += `<div class="step-reasoning" style="font-style:normal">${escapeHtml(evt.reasoning.slice(0, 500))}</div>`;
            }
            step.innerHTML = html;
        } else {
            const badge = badges[evt.severity] || badges.low;
            const argsStr = Object.entries(evt.args || {})
                .map(([k, v]) => {
                    const val = typeof v === "string" && v.length > 60
                        ? v.slice(0, 60) + "..." : v;
                    return `${k}: ${val}`;
                })
                .join(", ");

            let html = `<div class="step-header">
                <span class="severity-badge">${badge}</span>
                <span class="step-tool">${escapeHtml(evt.tool)}</span>
                <span class="step-args">${escapeHtml(argsStr)}</span>
            </div>`;

            if (evt.reasoning) {
                html += `<div class="step-reasoning">${escapeHtml(evt.reasoning)}</div>`;
            }
            if (evt.result) {
                html += `<div class="step-result">${escapeHtml(evt.result.slice(0, 300))}</div>`;
            }
            step.innerHTML = html;
        }

        steps.appendChild(step);
    }

    toggle.addEventListener("click", () => {
        steps.classList.toggle("hidden");
        const arrow = toggle.querySelector(".thought-arrow");
        arrow.textContent = steps.classList.contains("hidden")
            ? "expand_more" : "expand_less";
    });

    container.appendChild(toggle);
    container.appendChild(steps);
    return container;
}


/* --- Copy button on code blocks ---
   Added after markdown render on every <pre> block.
   Ref: https://developer.mozilla.org/en-US/docs/Web/API/Clipboard/writeText */

function addCopyButtons(container) {
    container.querySelectorAll("pre").forEach(pre => {
        const wrapper = document.createElement("div");
        wrapper.className = "code-block-wrapper";
        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(pre);

        const btn = document.createElement("button");
        btn.className = "copy-btn";
        btn.title = "Copy code";
        btn.innerHTML = '<span class="material-symbols-rounded">content_copy</span>';

        btn.addEventListener("click", () => {
            const code = pre.querySelector("code");
            navigator.clipboard.writeText(code ? code.textContent : pre.textContent);
            btn.innerHTML = '<span class="material-symbols-rounded">check</span>';
            setTimeout(() => {
                btn.innerHTML = '<span class="material-symbols-rounded">content_copy</span>';
            }, 2000);
        });

        wrapper.appendChild(btn);
    });
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        $messages.scrollTop = $messages.scrollHeight;
    });
}


/* --- Error with regenerate button --- */

function buildErrorWithRetry(message) {
    const wrapper = document.createElement("div");

    const errDiv = document.createElement("div");
    errDiv.className = "msg-error";
    errDiv.textContent = message;

    const retryBtn = document.createElement("button");
    retryBtn.className = "regenerate-btn";
    retryBtn.innerHTML = '<span class="material-symbols-rounded">refresh</span> Retry';
    retryBtn.addEventListener("click", () => {
        /* -- Remove this error message row -- */
        const msgRow = wrapper.closest(".msg");
        if (msgRow) msgRow.remove();
        /* -- Re-send the last message -- */
        if (lastSentMessage) {
            sendMessage(lastSentMessage);
        }
    });

    wrapper.appendChild(errDiv);
    wrapper.appendChild(retryBtn);
    return wrapper;
}


/* --- Toast notification --- */

function showToast(message, type = "") {
    let toast = document.getElementById("toast-notification");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "toast-notification";
        toast.className = "toast";
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.className = "toast" + (type ? ` ${type}` : "");
    requestAnimationFrame(() => {
        toast.classList.add("visible");
    });
    setTimeout(() => {
        toast.classList.remove("visible");
    }, 4000);
}


/* --- Loading indicator --- */

function showLoading() {
    const row = document.createElement("div");
    row.className = "msg assistant";
    row.id = "loading-msg";

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    const icon = document.createElement("span");
    icon.className = "material-symbols-rounded";
    icon.textContent = "smart_toy";
    avatar.appendChild(icon);

    const dots = document.createElement("div");
    dots.className = "typing-dots";
    dots.innerHTML = "<span></span><span></span><span></span>";

    row.appendChild(avatar);
    row.appendChild(dots);
    $messages.appendChild(row);
    scrollToBottom();
}

function hideLoading() {
    const el = document.getElementById("loading-msg");
    if (el) el.remove();
}


/* --- Send message (streaming via SSE) ---
   Sends to the streaming endpoint. Tool events appear in real-time,
   final answer streams token by token.
   Ref: https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch
   Ref: https://developer.mozilla.org/en-US/docs/Web/API/ReadableStream */

async function sendMessage(overrideText) {
    const text = overrideText || $input.value.trim();
    if (!text || !activeChatId) return;

    /* -- Store for retry -- */
    lastSentMessage = text;

    /* -- Clear input and reset height -- */
    if (!overrideText) {
        $input.value = "";
        $input.style.height = "auto";
    }

    /* -- Show user message immediately (skip if retrying) -- */
    if (!overrideText) {
        appendMessage("user", text);
    }
    scrollToBottom();

    /* -- Show typing indicator -- */
    showLoading();

    const settings = loadSettings();
    const payload = {
        content: text,
        context_window: settings.contextWindow,
        internet_enabled: internetEnabled,
        confirmation_mode: confirmationMode,
        thinking_enabled: thinkingEnabled,
    };

    try {
        const res = await fetch(`/api/chats/${activeChatId}/messages/stream`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }

        hideLoading();

        /* -- Create the assistant message bubble for streaming -- */
        const row = document.createElement("div");
        row.className = "msg assistant";

        const avatar = document.createElement("div");
        avatar.className = "msg-avatar";
        const icon = document.createElement("span");
        icon.className = "material-symbols-rounded";
        icon.textContent = "smart_toy";
        avatar.appendChild(icon);

        const body = document.createElement("div");
        body.className = "msg-content";

        const contentDiv = document.createElement("div");
        contentDiv.className = "streaming-content";

        const cursor = document.createElement("span");
        cursor.className = "streaming-cursor";

        body.appendChild(contentDiv);
        row.appendChild(avatar);
        row.appendChild(body);
        $messages.appendChild(row);

        /* -- Read the SSE stream -- */
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = "";
        let toolEvents = [];
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop(); // keep incomplete line

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const jsonStr = line.slice(6);
                if (!jsonStr.trim()) continue;

                let event;
                try { event = JSON.parse(jsonStr); }
                catch { continue; }

                switch (event.type) {
                    case "thinking_blocked":
                        showToast(`Thinking disabled - ${event.model} does not support it`, "warn");
                        break;

                    case "thinking":
                        toolEvents.push({
                            tool: "_thinking",
                            args: {},
                            reasoning: event.content || "",
                            result: "",
                            severity: "low",
                        });
                        break;

                    case "tool":
                        toolEvents.push({
                            tool: event.tool,
                            args: event.args || {},
                            reasoning: event.reasoning || "",
                            result: "running...",
                            severity: event.severity || "low",
                        });
                        /* -- Show tool activity indicator -- */
                        contentDiv.innerHTML = `<span style="color:var(--muted);font-size:13px">Using ${escapeHtml(event.tool)}...</span>`;
                        cursor.remove();
                        contentDiv.appendChild(cursor);
                        scrollToBottom();
                        break;

                    case "tool_result":
                        /* -- Update last tool event with result -- */
                        for (let i = toolEvents.length - 1; i >= 0; i--) {
                            if (toolEvents[i].tool === event.tool) {
                                toolEvents[i].result = event.result || "";
                                break;
                            }
                        }
                        break;

                    case "token":
                        fullContent += event.content;
                        contentDiv.innerHTML = renderMarkdown(fullContent);
                        cursor.remove();
                        contentDiv.appendChild(cursor);
                        scrollToBottom();
                        break;

                    case "done":
                        fullContent = event.content || fullContent;
                        toolEvents = event.tool_events || toolEvents;

                        /* -- Final render with thought process + copy buttons -- */
                        cursor.remove();
                        body.innerHTML = "";

                        if (toolEvents.length > 0) {
                            body.appendChild(renderThoughtProcess(toolEvents));
                        }

                        const finalDiv = document.createElement("div");
                        finalDiv.innerHTML = renderMarkdown(fullContent);
                        body.appendChild(finalDiv);
                        addCopyButtons(finalDiv);

                        /* -- Update chat title -- */
                        if (event.chat) {
                            const chat = chats.find(c => c.id === activeChatId);
                            if (chat && chat.title !== event.chat.title) {
                                chat.title = event.chat.title;
                                renderChatList();
                            }
                        }
                        scrollToBottom();
                        break;

                    case "error":
                        cursor.remove();
                        contentDiv.innerHTML = "";
                        body.innerHTML = "";
                        body.appendChild(buildErrorWithRetry(event.content || "Unknown error"));
                        scrollToBottom();
                        break;
                }
            }
        }

        /* -- If stream ended without a done event, finalize -- */
        if (fullContent && !contentDiv.querySelector(".streaming-cursor")) {
            /* Already finalized by done event */
        } else if (fullContent) {
            cursor.remove();
            contentDiv.innerHTML = renderMarkdown(fullContent);
            addCopyButtons(contentDiv);
        }

    } catch (e) {
        hideLoading();
        /* -- Build error with retry button -- */
        const row = document.createElement("div");
        row.className = "msg assistant";
        const avatar = document.createElement("div");
        avatar.className = "msg-avatar";
        const ic = document.createElement("span");
        ic.className = "material-symbols-rounded";
        ic.textContent = "smart_toy";
        avatar.appendChild(ic);
        const errBody = document.createElement("div");
        errBody.className = "msg-content";
        errBody.appendChild(buildErrorWithRetry(`Error: ${e.message}`));
        row.appendChild(avatar);
        row.appendChild(errBody);
        $messages.appendChild(row);
        scrollToBottom();
    }
}


/* --- Auto-grow textarea ---
   Ref: https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement/style */

$input.addEventListener("input", () => {
    $input.style.height = "auto";
    $input.style.height = Math.min($input.scrollHeight, 200) + "px";
});

/* -- Submit on Enter, newline on Shift+Enter -- */
$input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});


/* --- Agent label --- */

function updateAgentLabel() {
    const chat = chats.find(c => c.id === activeChatId);
    if (!chat) return;
    const agent = agents.find(a => a.key === chat.agent);
    $agentLabel.textContent = agent ? agent.name : chat.agent;
}


/* --- Dropdowns ---
   Positioned above their trigger button using getBoundingClientRect.
   Click-outside closes all dropdowns.
   Ref: https://developer.mozilla.org/en-US/docs/Web/API/Element/getBoundingClientRect */

function positionDropdown(dropdown, triggerBtn) {
    const rect = triggerBtn.getBoundingClientRect();
    dropdown.style.bottom = (window.innerHeight - rect.top + 8) + "px";
    dropdown.style.left = Math.max(8, rect.left) + "px";
}

function toggleDropdown(dropdown, triggerBtn) {
    const isOpen = !dropdown.classList.contains("hidden");
    closeAllDropdowns();
    if (!isOpen) {
        positionDropdown(dropdown, triggerBtn);
        dropdown.classList.remove("hidden");
    }
}

function closeAllDropdowns() {
    $agentDropdown.classList.add("hidden");
    $settingsDD.classList.add("hidden");
    $filesDD.classList.add("hidden");
}

/* -- Close on click outside -- */
document.addEventListener("click", (e) => {
    if (!e.target.closest(".dropdown") &&
        !e.target.closest("#btn-agent") &&
        !e.target.closest("#btn-settings") &&
        !e.target.closest("#btn-attach")) {
        closeAllDropdowns();
    }
});

/* -- Agent button -- */
document.getElementById("btn-agent").addEventListener("click", (e) => {
    e.stopPropagation();
    populateAgentDropdown();
    toggleDropdown($agentDropdown, e.currentTarget);
});

/* -- Settings button -- */
document.getElementById("btn-settings").addEventListener("click", (e) => {
    e.stopPropagation();
    populateShowcase();
    toggleDropdown($settingsDD, e.currentTarget);
});

/* -- Send button -- */
document.getElementById("btn-send").addEventListener("click", sendMessage);


/* --- Internet toggle ---
   ON = agents get web_search + GitHub tools. OFF = local only.
   Ref: https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage */

const $internetBtn = document.getElementById("btn-internet");

function updateInternetButton() {
    const icon = $internetBtn.querySelector(".material-symbols-rounded");
    if (internetEnabled) {
        $internetBtn.classList.add("active");
        $internetBtn.title = "Internet search enabled";
        icon.textContent = "language";
    } else {
        $internetBtn.classList.remove("active");
        $internetBtn.title = "Internet search disabled";
        icon.textContent = "language";
    }
}

$internetBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    internetEnabled = !internetEnabled;
    localStorage.setItem("qm_internet", String(internetEnabled));
    updateInternetButton();
});


/* --- Confirmation toggle ---
   ON = agent asks before write/modify operations. OFF = executes freely.
   Ref: https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage */

const $confirmBtn = document.getElementById("btn-confirm");

function updateConfirmButton() {
    if (confirmationMode) {
        $confirmBtn.classList.add("active");
        $confirmBtn.title = "Confirmation mode on - agent asks before changes";
    } else {
        $confirmBtn.classList.remove("active");
        $confirmBtn.title = "Confirmation mode off";
    }
}

$confirmBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    confirmationMode = !confirmationMode;
    localStorage.setItem("qm_confirm", String(confirmationMode));
    updateConfirmButton();
});


/* --- Thinking toggle ---
   ON = agents use chain-of-thought reasoning. OFF = fast direct answers.
   Per-agent default can be overridden by this toggle.
   Ref: https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage */

const $thinkingBtn = document.getElementById("btn-thinking");

function updateThinkingButton() {
    if (thinkingEnabled) {
        $thinkingBtn.classList.add("active");
        $thinkingBtn.title = "Thinking mode on - agent reasons step by step";
    } else {
        $thinkingBtn.classList.remove("active");
        $thinkingBtn.title = "Thinking mode off";
    }
}

$thinkingBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    /* -- Block toggle if model doesn't support thinking -- */
    if ($thinkingBtn.classList.contains("disabled")) {
        showToast("Current model does not support thinking mode", "warn");
        return;
    }
    thinkingEnabled = !thinkingEnabled;
    localStorage.setItem("qm_thinking", String(thinkingEnabled));
    updateThinkingButton();
});

/* -- Update thinking toggle when agent changes (respect agent defaults) -- */
function syncThinkingWithAgent() {
    const chat = chats.find(c => c.id === activeChatId);
    if (!chat) return;
    const agent = agents.find(a => a.key === chat.agent);
    if (agent && agent.thinking_default !== undefined) {
        /* -- Only auto-set if user hasn't explicitly toggled -- */
        const userOverride = localStorage.getItem("qm_thinking_override");
        if (userOverride !== "true") {
            thinkingEnabled = agent.thinking_default;
            localStorage.setItem("qm_thinking", String(thinkingEnabled));
            updateThinkingButton();
        }
    }
}


/* --- Voice input (Web Speech API) ---
   Uses the browser's built-in speech recognition (Chrome/Edge).
   Transcribed text is inserted into the input field.
   Ref: https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition */

const $micBtn = document.getElementById("btn-mic");

function initVoiceInput() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        $micBtn.style.display = "none";
        $micBtn.title = "Voice input not supported in this browser";
        return;
    }

    speechRecognition = new SpeechRecognition();
    speechRecognition.continuous = false;
    speechRecognition.interimResults = true;
    speechRecognition.lang = navigator.language || "en-US";

    let finalTranscript = "";

    speechRecognition.onstart = () => {
        isRecording = true;
        $micBtn.classList.add("recording");
        $micBtn.title = "Listening... (click to stop)";
    };

    speechRecognition.onresult = (event) => {
        let interim = "";
        finalTranscript = "";
        for (let i = 0; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
                finalTranscript += event.results[i][0].transcript;
            } else {
                interim += event.results[i][0].transcript;
            }
        }
        /* -- Show interim results in the input field -- */
        $input.value = finalTranscript + interim;
        $input.style.height = "auto";
        $input.style.height = Math.min($input.scrollHeight, 200) + "px";
    };

    speechRecognition.onend = () => {
        isRecording = false;
        $micBtn.classList.remove("recording");
        $micBtn.title = "Voice input";
        /* -- If we got a final transcript, keep it in the input -- */
        if (finalTranscript.trim()) {
            $input.value = finalTranscript.trim();
            $input.focus();
        }
    };

    speechRecognition.onerror = (event) => {
        isRecording = false;
        $micBtn.classList.remove("recording");
        $micBtn.title = "Voice input";
        const errMap = {
            "not-allowed": "Microphone access denied. Allow it in browser settings.",
            "no-speech": "",
            "aborted": "",
            "network": "Network error. Speech recognition needs an internet connection.",
            "service-not-allowed": "Speech service not available. Try Chrome or Edge.",
        };
        const msg = errMap[event.error];
        if (msg === undefined) {
            showToast(`Mic error: ${event.error}`, "warn");
        } else if (msg) {
            showToast(msg, "warn");
        }
    };
}

$micBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    if (!speechRecognition) {
        showToast("Voice input not supported. Use Chrome or Edge.", "warn");
        return;
    }

    if (isRecording) {
        speechRecognition.stop();
    } else {
        try {
            speechRecognition.start();
        } catch (err) {
            showToast(`Mic error: ${err.message}`, "warn");
        }
    }
});


/* --- Profile selector --- */

const $profileSelect = document.getElementById("profile-select");
const $profileInfo = document.getElementById("profile-info");

function initProfileSelector() {
    $profileSelect.value = activeProfile;

    /* -- Fetch system info to show detected profile -- */
    api("/system-info").then(info => {
        if (activeProfile === "auto") {
            $profileInfo.textContent = `Detected: ${info.detected_profile} (${info.ram_gb || "?"}GB RAM, ${info.cpu_cores || "?"}cores)`;
        }
    }).catch(() => {});
}

$profileSelect.addEventListener("change", () => {
    activeProfile = $profileSelect.value;
    localStorage.setItem("qm_profile", activeProfile);

    /* -- Auto-adjust context window based on profile -- */
    if (activeProfile === "lite") {
        $ctxSelect.value = "2048";
    } else if (activeProfile === "standard") {
        $ctxSelect.value = "4096";
    } else if (activeProfile === "full") {
        $ctxSelect.value = "8192";
    }
    const s = loadSettings();
    s.contextWindow = parseInt($ctxSelect.value, 10);
    saveSettings(s);

    /* -- Update profile info -- */
    api("/profiles").then(data => {
        const p = data.profiles[activeProfile] || data.profiles[data.detected];
        if (p) $profileInfo.textContent = p.description;
    }).catch(() => {});
});


/* --- Agent dropdown: populate + handle selection --- */

async function populateAgentDropdown() {
    const chat = chats.find(c => c.id === activeChatId);
    if (!chat) return;

    /* -- Agent radio list -- */
    $agentList.innerHTML = "";
    for (const a of agents) {
        const btn = document.createElement("button");
        btn.className = "agent-option" + (a.key === chat.agent ? " active" : "");
        btn.innerHTML = `
            <span class="material-symbols-rounded" style="color: var(--accent)">smart_toy</span>
            <span>${a.name}</span>
            <span class="material-symbols-rounded check">check</span>
        `;
        btn.addEventListener("click", () => pickAgent(a.key));
        $agentList.appendChild(btn);
    }

    /* -- Model select (with thinking support info) -- */
    try {
        const data = await api("/models");
        $modelSelect.innerHTML = "";
        modelThinkingSupport = {};
        for (const m of data.models) {
            modelThinkingSupport[m.name] = m.thinks;
            const opt = document.createElement("option");
            opt.value = m.name;
            opt.textContent = m.name + (m.thinks ? " \u{1F9E0}" : "");
            if (m.name === chat.model) opt.selected = true;
            $modelSelect.appendChild(opt);
        }
        updateThinkingAvailability(chat.model);
    } catch {
        $modelSelect.innerHTML = `<option>${chat.model} (Ollama unreachable)</option>`;
    }
}

async function pickAgent(agentKey) {
    if (!activeChatId) return;
    try {
        const updated = await api(`/chats/${activeChatId}`, {
            method: "PATCH",
            body: JSON.stringify({ agent: agentKey }),
        });
        const chat = chats.find(c => c.id === activeChatId);
        if (chat) {
            chat.agent = updated.agent;
            chat.model = updated.model;
        }
        updateAgentLabel();
        populateAgentDropdown();
    } catch (e) {
        console.error("Agent switch failed:", e);
    }
}

/* -- Model override -- */
$modelSelect.addEventListener("change", async () => {
    if (!activeChatId) return;
    try {
        const updated = await api(`/chats/${activeChatId}`, {
            method: "PATCH",
            body: JSON.stringify({ model: $modelSelect.value }),
        });
        const chat = chats.find(c => c.id === activeChatId);
        if (chat) chat.model = updated.model;
        updateThinkingAvailability($modelSelect.value);
    } catch (e) {
        console.error("Model change failed:", e);
    }
});


/* --- Thinking availability based on model ---
   Disables the thinking toggle when the current model doesn't support it. */

function updateThinkingAvailability(modelName) {
    const canThink = modelThinkingSupport[modelName] === true;
    if (canThink) {
        $thinkingBtn.classList.remove("disabled");
        $thinkingBtn.title = thinkingEnabled
            ? "Thinking mode on" : "Thinking mode off";
    } else {
        $thinkingBtn.classList.add("disabled");
        $thinkingBtn.title = "Model does not support thinking";
        /* -- Auto-disable thinking for this model -- */
        if (thinkingEnabled) {
            thinkingEnabled = false;
            localStorage.setItem("qm_thinking", "false");
            updateThinkingButton();
        }
    }
}


/* --- Settings dropdown --- */

function initSettingsControls() {
    const s = loadSettings();
    $themeSelect.value = s.theme;
    $fontSelect.value  = s.font;
    $ctxSelect.value   = String(s.contextWindow);

    $themeSelect.addEventListener("change", () => {
        const s = loadSettings();
        s.theme = $themeSelect.value;
        saveSettings(s);
        applyTheme(s.theme);
    });

    $fontSelect.addEventListener("change", () => {
        const s = loadSettings();
        s.font = $fontSelect.value;
        saveSettings(s);
        applyFont(s.font);
    });

    $ctxSelect.addEventListener("change", () => {
        const s = loadSettings();
        s.contextWindow = parseInt($ctxSelect.value, 10);
        saveSettings(s);
    });
}

function populateShowcase() {
    const chat = chats.find(c => c.id === activeChatId);
    if (!chat) { $showcase.innerHTML = ""; return; }

    const agent = agents.find(a => a.key === chat.agent);
    let html = "";
    html += `<div><span class="showcase-label">Agent:</span> ${agent ? agent.name : chat.agent}</div>`;
    html += `<div><span class="showcase-label">Model:</span> ${chat.model}</div>`;
    if (agent) {
        html += `<div><span class="showcase-label">Temperature:</span> ${agent.temperature}</div>`;
        if (agent.tools.length) {
            html += `<div><span class="showcase-label">Tools:</span></div>`;
            for (const t of agent.tools) {
                html += `<div>&nbsp;&nbsp;• ${t}</div>`;
            }
        }
    }
    $showcase.innerHTML = html;

    /* -- DB info for SQL agent -- */
    if (chat.agent === "sql") {
        api("/db-info").then(data => {
            if (data.tables && data.tables.length) {
                let dbHtml = `<hr class="dropdown-divider"><div class="dropdown-header" style="padding-top:8px">Database</div>`;
                for (const t of data.tables) {
                    dbHtml += `<div>${t.name} - ${t.rows.toLocaleString()} rows</div>`;
                }
                $showcase.innerHTML += dbHtml;
            }
        }).catch(() => {});
    }
}


/* --- Sidebar toggle --- */

document.getElementById("btn-sidebar-open").addEventListener("click", () => {
    document.body.classList.remove("sidebar-collapsed");
    document.body.dataset.sidebarState = "";
});

document.getElementById("btn-sidebar-close").addEventListener("click", () => {
    document.body.classList.add("sidebar-collapsed");
    document.body.dataset.sidebarState = "collapsed";
});


/* --- New Chat button --- */

document.getElementById("btn-new-chat").addEventListener("click", createNewChat);


/* --- File uploads ---
   Files are saved to workspace/uploads/ on the server.
   Agents can read them with read_file("uploads/filename") and
   list them with list_files("uploads").
   Ref: https://developer.mozilla.org/en-US/docs/Web/API/FormData */

/* -- Attach button opens file dropdown -- */
document.getElementById("btn-attach").addEventListener("click", (e) => {
    e.stopPropagation();
    refreshFileList();
    toggleDropdown($filesDD, e.currentTarget);
});

/* -- Upload button inside dropdown triggers the hidden file input -- */
document.getElementById("btn-upload").addEventListener("click", () => {
    $fileInput.click();
});

/* -- When files are picked, upload each one -- */
$fileInput.addEventListener("change", async () => {
    for (const file of $fileInput.files) {
        await uploadFile(file);
    }
    $fileInput.value = "";
    refreshFileList();
});

async function uploadFile(file) {
    const formData = new FormData();
    formData.append("file", file);
    try {
        const res = await fetch("/api/uploads", {
            method: "POST",
            body: formData,
        });
        if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    } catch (e) {
        console.error("Upload error:", e);
    }
}

async function refreshFileList() {
    try {
        const files = await api("/uploads");
        renderFileList(files);
        updateUploadBadge(files.length);
    } catch (e) {
        console.error("Failed to list uploads:", e);
    }
}

function renderFileList(files) {
    $fileList.innerHTML = "";
    if (files.length === 0) {
        $fileList.innerHTML = '<span class="muted-text">No files uploaded</span>';
        return;
    }
    for (const f of files) {
        const row = document.createElement("div");
        row.className = "file-row";

        const icon = document.createElement("span");
        icon.className = "material-symbols-rounded";
        icon.textContent = "description";
        icon.style.fontSize = "16px";
        icon.style.color = "var(--muted)";

        const name = document.createElement("span");
        name.className = "file-name";
        name.textContent = f.name;

        const size = document.createElement("span");
        size.className = "file-size";
        size.textContent = formatSize(f.size);

        const del = document.createElement("button");
        del.className = "file-delete";
        del.title = "Delete file";
        del.innerHTML = '<span class="material-symbols-rounded" style="font-size:16px">close</span>';
        del.addEventListener("click", async (e) => {
            e.stopPropagation();
            await deleteUpload(f.name);
        });

        row.appendChild(icon);
        row.appendChild(name);
        row.appendChild(size);
        row.appendChild(del);
        $fileList.appendChild(row);
    }
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function updateUploadBadge(count) {
    if (count > 0) {
        $uploadBadge.textContent = count;
        $uploadBadge.classList.remove("hidden");
    } else {
        $uploadBadge.classList.add("hidden");
    }
}

async function deleteUpload(filename) {
    try {
        await api(`/uploads/${encodeURIComponent(filename)}`, {
            method: "DELETE",
        });
        refreshFileList();
    } catch (e) {
        console.error("Delete failed:", e);
    }
}


/* --- Drag-and-drop file upload ---
   Dragging files anywhere over #main shows an overlay.
   Dropping uploads them via the existing /api/uploads endpoint.
   Ref: https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API */

const $main        = document.getElementById("main");
const $dropOverlay = document.getElementById("drop-overlay");
let dragCounter    = 0;

/* -- Show overlay on drag enter -- */
$main.addEventListener("dragenter", (e) => {
    e.preventDefault();
    dragCounter++;
    $main.classList.add("drag-active");
    $dropOverlay.classList.add("visible");
});

/* -- Keep overlay visible while dragging over -- */
$main.addEventListener("dragover", (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
});

/* -- Hide overlay when drag leaves -- */
$main.addEventListener("dragleave", (e) => {
    e.preventDefault();
    dragCounter--;
    if (dragCounter <= 0) {
        dragCounter = 0;
        $main.classList.remove("drag-active");
        $dropOverlay.classList.remove("visible");
    }
});

/* -- Handle dropped files -- */
$main.addEventListener("drop", async (e) => {
    e.preventDefault();
    dragCounter = 0;
    $main.classList.remove("drag-active");
    $dropOverlay.classList.remove("visible");

    const files = e.dataTransfer.files;
    if (!files.length) return;

    for (const file of files) {
        await uploadFile(file);
    }
    refreshFileList();
});


/* --- Init ---
   Load agents + chats from the API, apply saved settings, render. */

async function init() {
    /* -- Apply saved settings -- */
    const s = loadSettings();
    applyTheme(s.theme);
    applyFont(s.font);
    initSettingsControls();
    updateInternetButton();
    updateConfirmButton();
    updateThinkingButton();
    initVoiceInput();
    initProfileSelector();

    /* -- Collapse sidebar on mobile by default -- */
    if (window.innerWidth <= 768) {
        document.body.classList.add("sidebar-collapsed");
        document.body.dataset.sidebarState = "collapsed";
    }

    /* -- Load agents -- */
    try {
        agents = await api("/agents");
    } catch (e) {
        console.error("Failed to load agents:", e);
        agents = [];
    }

    /* -- Load chats -- */
    try {
        chats = await api("/chats");
    } catch (e) {
        console.error("Failed to load chats:", e);
        chats = [];
    }

    /* -- Load upload badge count -- */
    refreshFileList();

    /* -- If no chats, create one -- */
    if (chats.length === 0) {
        await createNewChat();
    } else {
        await switchChat(chats[0].id);
    }
}

init();
