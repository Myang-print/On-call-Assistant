import "./styles.css";
import { queryOnCall } from "./api/oncall.ts";

const STORAGE_KEY = "ONCALL_SESSION_V3";

const modeAssets = {
  exact: {
    label: "exact",
    title: "exact search workspace",
    description: "Backend-connected keyword mode request.",
    image: new URL("../Figure/Andante.png", import.meta.url).href
  },
  semantic: {
    label: "semantic",
    title: "semantic search workspace",
    description: "Backend-connected semantic mode request.",
    image: new URL("../Figure/Moderato.png", import.meta.url).href
  },
  agent: {
    label: "agent",
    title: "agent response workspace",
    description: "Backend-connected agent answer with trace playback.",
    image: new URL("../Figure/Allegretto.png", import.meta.url).href
  }
};

document.querySelector("#app").innerHTML = `
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-left">
        <button class="icon-button" type="button" aria-label="Toggle sidebar">▌▌</button>
        <button class="icon-button" type="button" data-new-chat aria-label="New chat">＋</button>
        <button class="workspace-name" type="button">OnCallAgent <span class="soft-chevron"></span></button>
      </div>
      <button class="icon-button icon-share" type="button" aria-label="Share">
        <span class="soft-arrow soft-arrow-share"></span>
      </button>
    </header>

    <main class="workspace">
      <section class="conversation">
        <article class="hero-copy">
          <p class="system-line">Backend console is ready.</p>
          <h1 data-mode-title></h1>
          <p data-mode-copy></p>
        </article>

        <section class="version-showcase" data-version-card>
          <img data-version-image alt="Version artwork" />
        </section>

        <section class="session-strip">
          <button type="button" data-new-chat>New Chat</button>
          <div class="session-list" data-session-list></div>
        </section>

        <section class="answer-surface" data-answer-surface></section>

        <form class="composer" data-composer>
          <div
            class="composer-textarea"
            contenteditable="true"
            role="textbox"
            data-placeholder="Ask an on-call question..."
            aria-label="Query input"
          ></div>
          <div class="composer-toolbar">
            <div class="composer-left">
              <button class="add-button" type="button" data-add-toggle aria-label="Add document">＋</button>
              <div class="upload-popover" data-add-menu hidden>
                <div class="upload-title">
                  <span>⌘</span>
                  <strong>Upload File</strong>
                </div>
                <button class="upload-dropzone" type="button" data-upload-dropzone>
                  <span class="upload-cloud">☁</span>
                  <span>Drag & drop file here</span>
                  <small>or click to browse</small>
                </button>
                <p data-upload-status>Supports .html, .txt, .md, .log, .json</p>
              </div>
              <input class="file-input" data-file-input type="file" accept=".html,.txt,.md,.log,.json,text/html,text/plain,application/json" aria-label="Upload file" />
            </div>
            <div class="composer-right">
              <div class="mode-selector">
                <button class="mode-button" type="button" data-mode-toggle>
                  <span data-current-mode></span>
                  <span class="soft-chevron"></span>
                </button>
                <div class="mode-menu" data-mode-menu hidden>
                  <button type="button" data-mode="exact">
                    <span>
                      <strong>exact</strong>
                      <small>Keyword result list</small>
                    </span>
                    <b data-check="exact"></b>
                  </button>
                  <button type="button" data-mode="semantic">
                    <span>
                      <strong>semantic</strong>
                      <small>Semantic request mode</small>
                    </span>
                    <b data-check="semantic"></b>
                  </button>
                  <button type="button" data-mode="agent">
                    <span>
                      <strong>agent</strong>
                      <small>Backend answer and trace</small>
                    </span>
                    <b data-check="agent"></b>
                  </button>
                </div>
              </div>
              <button class="send-button" type="submit" aria-label="Submit query">
                <span class="soft-arrow soft-arrow-up"></span>
              </button>
            </div>
          </div>
        </form>
      </section>

      <aside class="trace-panel">
        <div class="trace-header">
          <div>
            <p>Trace</p>
            <h2>Execution Path</h2>
          </div>
          <span data-trace-count>0 steps</span>
        </div>
        <div class="trace-list" data-trace-list></div>
      </aside>
    </main>
  </div>
`;

let appState = loadState();

const answerSurface = document.querySelector("[data-answer-surface]");
const traceList = document.querySelector("[data-trace-list]");
const traceCount = document.querySelector("[data-trace-count]");
const modeMenu = document.querySelector("[data-mode-menu]");
const addMenu = document.querySelector("[data-add-menu]");
const fileInput = document.querySelector("[data-file-input]");
const uploadDropzone = document.querySelector("[data-upload-dropzone]");
const uploadStatus = document.querySelector("[data-upload-status]");
const sendButton = document.querySelector(".send-button");
const composerInput = document.querySelector(".composer-textarea");
const sessionList = document.querySelector("[data-session-list]");

document.querySelector("[data-mode-toggle]").addEventListener("click", () => {
  modeMenu.hidden = !modeMenu.hidden;
  addMenu.hidden = true;
});

document.querySelectorAll("[data-new-chat]").forEach((button) => {
  button.addEventListener("click", () => {
    const session = createSession();
    appState.sessions.unshift(session);
    appState.activeSessionId = session.id;
    saveState();
    composerInput.textContent = "";
    renderApp();
  });
});

document.querySelector("[data-add-toggle]").addEventListener("click", () => {
  addMenu.hidden = !addMenu.hidden;
  modeMenu.hidden = true;
});

uploadDropzone.addEventListener("click", () => {
  fileInput.click();
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  uploadStatus.textContent = file ? `Selected: ${file.name}` : "Supports .html, .txt, .md, .log, .json";
});

uploadDropzone.addEventListener("dragover", (event) => {
  event.preventDefault();
  uploadDropzone.classList.add("is-dragging");
});

uploadDropzone.addEventListener("dragleave", () => {
  uploadDropzone.classList.remove("is-dragging");
});

uploadDropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  uploadDropzone.classList.remove("is-dragging");
  const file = event.dataTransfer.files?.[0];
  uploadStatus.textContent = file ? `Selected: ${file.name}` : "Supports .html, .txt, .md, .log, .json";
});

document.querySelectorAll("[data-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    const session = getActiveSession();
    session.mode = button.dataset.mode;
    session.updatedAt = Date.now();
    modeMenu.hidden = true;
    saveState();
    renderApp();
  });
});

sessionList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-session-id]");
  if (!button) {
    return;
  }
  appState.activeSessionId = button.dataset.sessionId;
  saveState();
  renderApp();
});

composerInput.addEventListener("input", () => {
  composerInput.classList.toggle("has-input", composerInput.innerText.trim().length > 0);
});

document.querySelector("[data-composer]").addEventListener("submit", (event) => {
  event.preventDefault();
  void submitQuery();
});

async function submitQuery() {
  const query = composerInput.innerText.trim();
  if (!query || sendButton.classList.contains("is-loading")) {
    composerInput.classList.toggle("is-empty", !query);
    return;
  }

  const session = getActiveSession();
  const mode = session.mode;
  session.messages.push({ role: "user", content: query, mode, createdAt: Date.now() });
  session.title = query.slice(0, 28);
  session.latestQuestion = query;
  session.answer = "";
  session.sources = [];
  session.trace = [];
  session.error = "";
  session.updatedAt = Date.now();
  saveState();
  renderLoading();

  try {
    const response = await queryOnCall(query, mode);
    const activeSession = getActiveSession();
    activeSession.latestQuestion = query;
    activeSession.answer = response.answer;
    activeSession.trace = response.trace ?? [];
    activeSession.sources = response.sources ?? [];
    activeSession.error = "";
    activeSession.updatedAt = Date.now();
    composerInput.textContent = "";
    composerInput.classList.remove("has-input", "is-empty");
    saveState();
    renderApp();
  } catch (error) {
    const activeSession = getActiveSession();
    activeSession.latestQuestion = query;
    activeSession.answer = "";
    activeSession.sources = [];
    activeSession.error = error instanceof Error ? error.message : "Request failed.";
    activeSession.trace = [
      {
        step: 0,
        event: "frontend_error",
        detail: error instanceof Error ? error.message : "unknown request error"
      }
    ];
    activeSession.updatedAt = Date.now();
    saveState();
    renderApp();
  }
}

renderApp();

function loadState() {
  try {
    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "null");
    if (stored?.sessions?.length && stored.activeSessionId) {
      return stored;
    }
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
  }

  const session = createSession();
  return {
    activeSessionId: session.id,
    sessions: [session]
  };
}

function saveState() {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(appState));
}

function createSession() {
  const now = Date.now();
  return {
    id: `session-${now}-${Math.random().toString(16).slice(2)}`,
    title: "New Chat",
    mode: "agent",
    messages: [],
    latestQuestion: "",
    answer: "",
    sources: [],
    trace: [],
    error: "",
    createdAt: now,
    updatedAt: now
  };
}

function getActiveSession() {
  let session = appState.sessions.find((item) => item.id === appState.activeSessionId);
  if (!session) {
    session = createSession();
    appState.sessions.unshift(session);
    appState.activeSessionId = session.id;
    saveState();
  }
  return session;
}

function renderApp() {
  const session = getActiveSession();
  const mode = modeAssets[session.mode];

  document.querySelector("[data-current-mode]").textContent = mode.label;
  document.querySelector("[data-mode-title]").textContent = mode.title;
  document.querySelector("[data-mode-copy]").textContent = mode.description;
  document.querySelector("[data-version-image]").src = mode.image;
  sendButton.classList.remove("is-loading");
  sendButton.removeAttribute("aria-busy");

  document.querySelectorAll("[data-check]").forEach((check) => {
    check.textContent = check.dataset.check === session.mode ? "✓" : "";
  });

  renderSessions();
  renderMessages(session);
  renderTrace(session.trace);
}

function renderSessions() {
  sessionList.innerHTML = appState.sessions
    .map(
      (session) => `
        <button
          type="button"
          data-session-id="${session.id}"
          class="${session.id === appState.activeSessionId ? "is-active" : ""}"
        >
          ${escapeHtml(session.title)}
        </button>
      `
    )
    .join("");
}

function renderMessages(session) {
  if (!session.messages.length && !session.answer && !session.error) {
    answerSurface.innerHTML = `
      <div class="empty-state">
        <p>${modeAssets[session.mode].label} mode selected.</p>
        <span>Submit a query to request the backend.</span>
      </div>
    `;
    return;
  }

  const userMessages = session.messages.map(renderMessage).join("");
  const answerPanel = session.answer || session.error ? renderAnswerPanel(session) : "";
  const historyPanel = userMessages ? `<section class="history-panel"><h2>History</h2>${userMessages}</section>` : "";
  answerSurface.innerHTML = `${answerPanel}${historyPanel}`;
}

function renderMessage(message) {
  if (message.role === "user") {
    return `<article class="message message-user">${escapeHtml(message.content)}</article>`;
  }

  return "";
}

function renderLoading() {
  sendButton.classList.add("is-loading");
  sendButton.setAttribute("aria-busy", "true");
  answerSurface.insertAdjacentHTML(
    "beforeend",
    `
      <article class="message message-assistant" data-loading-message>
        <div class="loading-state">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </article>
    `
  );
}

function renderAnswerPanel(session) {
  return `
    <article class="answer-panel">
      <span class="response-badge">${escapeHtml(session.mode)} response</span>
      <div class="latest-question">
        <span>Latest question</span>
        <p>${escapeHtml(session.latestQuestion || session.title || "")}</p>
      </div>
      <h2>Answer</h2>
      ${
        session.error
          ? `<p class="message-error">${escapeHtml(session.error)}</p>`
          : `<p class="answer-text">${escapeHtml(session.answer)}</p>`
      }
      ${renderSources(session.sources ?? [])}
      ${renderDebugPanel(session)}
    </article>
  `;
}

function renderSources(sources) {
  const rows = sources
    .map(
      (source) => `
        <li>
          <strong>${escapeHtml(source.id || source.filename || "source")}</strong>
          <span>${escapeHtml(source.title || source.snippet || "No source detail")}</span>
          ${source.score ? `<b>${escapeHtml(source.score)}</b>` : ""}
        </li>
      `
    )
    .join("");

  return `
    <div class="source-panel">
      <div class="source-header">
        <p>Sources</p>
        <span>${sources.length} items</span>
      </div>
      ${
        sources.length
          ? `<ul class="source-list">${rows}</ul>`
          : `<p class="source-empty">Backend returned no source list.</p>`
      }
    </div>
  `;
}

function renderDebugPanel(session) {
  return `
    <div class="debug-panel">
      <span>answer length: ${String(session.answer || "").length}</span>
      <span>trace count: ${(session.trace ?? []).length}</span>
      <span>sources count: ${(session.sources ?? []).length}</span>
    </div>
  `;
}

function renderTrace(traceItems) {
  traceCount.textContent = `${traceItems.length} steps`;
  traceList.innerHTML = traceItems
    .map(
      (item) => `
        <details class="trace-item" open>
          <summary>
            <span>${escapeHtml(item.step ?? "-")}</span>
            <strong>${escapeHtml(item.event || item.stage || "trace")}</strong>
          </summary>
          <p>${escapeHtml(item.detail || item.error || JSON.stringify(item))}</p>
        </details>
      `
    )
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
