/* --- QueryMaster — Frontend Logic ---
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

function appendMessage(role, content) {
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
        if (content.startsWith("Error:")) {
            body.innerHTML = `<div class="msg-error">${escapeHtml(content)}</div>`;
        } else {
            body.innerHTML = renderMarkdown(content);
        }
    } else {
        body.textContent = content;
    }

    row.appendChild(avatar);
    row.appendChild(body);
    $messages.appendChild(row);
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


/* --- Send message --- */

async function sendMessage() {
    const text = $input.value.trim();
    if (!text || !activeChatId) return;

    /* -- Clear input and reset height -- */
    $input.value = "";
    $input.style.height = "auto";

    /* -- Show user message immediately -- */
    appendMessage("user", text);
    scrollToBottom();

    /* -- Show typing indicator -- */
    showLoading();

    try {
        const settings = loadSettings();
        const data = await api(`/chats/${activeChatId}/messages`, {
            method: "POST",
            body: JSON.stringify({
                content: text,
                context_window: settings.contextWindow,
            }),
        });

        hideLoading();
        appendMessage("assistant", data.content);
        scrollToBottom();

        /* -- Update chat title in sidebar if it changed -- */
        if (data.chat) {
            const chat = chats.find(c => c.id === activeChatId);
            if (chat && chat.title !== data.chat.title) {
                chat.title = data.chat.title;
                renderChatList();
            }
        }
    } catch (e) {
        hideLoading();
        appendMessage("assistant", `Error: ${e.message}`);
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

    /* -- Model select -- */
    try {
        const data = await api("/models");
        $modelSelect.innerHTML = "";
        for (const m of data.models) {
            const opt = document.createElement("option");
            opt.value = m;
            opt.textContent = m;
            if (m === chat.model) opt.selected = true;
            $modelSelect.appendChild(opt);
        }
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
    } catch (e) {
        console.error("Model change failed:", e);
    }
});


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
                    dbHtml += `<div>${t.name} — ${t.rows.toLocaleString()} rows</div>`;
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
