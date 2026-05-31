import "./styles.css";
import { queryOnCall, uploadHtmlDocument } from "./api/oncall.ts";

const STORAGE_KEY = "ONCALL_SESSION_V4";

const modeAssets = {
  exact: {
    label: "exact",
    title: "exact search workspace",
    description: "Backend-connected keyword mode request.",
    image: "/Figure/Andante.png"
  },
  semantic: {
    label: "semantic",
    title: "semantic search workspace",
    description: "Backend-connected semantic mode request.",
    image: "/Figure/Moderato.png"
  },
  agent: {
    label: "agent",
    title: "agent response workspace",
    description: "Backend-connected agent answer with trace playback.",
    image: "/Figure/Allegretto.png"
  }
};

document.querySelector("#app").innerHTML = `
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-left">
        <div class="workspace-name">
          <span>OnCallAgent</span>
          <a
            href="https://www.moonshot.ai/"
            target="_blank"
            rel="noreferrer"
            aria-label="Open Moonshot AI"
          >
            <span class="soft-chevron"></span>
          </a>
        </div>
      </div>
      <a
        class="icon-button icon-share"
        href="https://github.com/Myang-print/On-call-Assistant.git"
        target="_blank"
        rel="noreferrer"
        aria-label="Open GitHub repository"
      >
        <span class="soft-arrow soft-arrow-share"></span>
      </a>
    </header>

    <main class="workspace">
      <aside class="history-panel">
        <div class="history-header">
          <p>History</p>
          <button type="button" data-history-toggle aria-label="Hide history">‹</button>
        </div>
        <div class="session-list" data-session-list></div>
      </aside>
      <button class="history-rail" type="button" data-history-toggle aria-label="Show history">History</button>

      <section class="conversation">
        <article class="hero-copy">
          <p class="system-line">Backend console is ready.</p>
          <h1 data-mode-title></h1>
          <p data-mode-copy></p>
        </article>

        <section class="version-showcase" data-version-card>
          <img data-version-image alt="Version artwork" />
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
                  <span class="upload-paperclip" aria-hidden="true"></span>
                  <strong>Upload File</strong>
                </div>
                <button class="upload-dropzone" type="button" data-upload-dropzone>
                  <span class="upload-cloud">☁</span>
                  <span>Drag & drop file here</span>
                  <small>or click to browse</small>
                </button>
                <p data-upload-status>Supports .html</p>
              </div>
              <input class="file-input" data-file-input type="file" accept=".html,text/html" aria-label="Upload file" />
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

    <div class="context-menu" data-context-menu hidden>
      <button type="button" data-delete-history>Delete</button>
    </div>
  </div>
`;

let appState = loadState();
let isHistoryOpen = false;

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
const contextMenu = document.querySelector("[data-context-menu]");
let pendingDelete = null;

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

document.querySelectorAll("[data-history-toggle]").forEach((button) => {
  button.addEventListener("click", () => {
    isHistoryOpen = !isHistoryOpen;
    renderHistoryVisibility();
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
  void handleUploadFile(file);
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
  void handleUploadFile(file);
});

async function handleUploadFile(file) {
  if (!file) {
    uploadStatus.textContent = "Supports .html";
    return;
  }

  uploadStatus.textContent = `Uploading: ${file.name}`;
  try {
    const document = await uploadHtmlDocument(file);
    uploadStatus.textContent = `Added: ${document.id}`;
  } catch (error) {
    uploadStatus.textContent = error instanceof Error ? error.message : "Upload failed.";
  } finally {
    fileInput.value = "";
  }
}

document.querySelectorAll("[data-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    const session = getActiveSession();
    session.mode = button.dataset.mode;
    appState.activeResponseId = "";
    session.trace = [];
    session.updatedAt = Date.now();
    modeMenu.hidden = true;
    saveState();
    renderApp();
  });
});

sessionList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-response-id]");
  if (!button) {
    return;
  }
  appState.activeSessionId = button.dataset.sessionId;
  appState.activeResponseId = button.dataset.responseId;
  const selectedSession = getActiveSession();
  selectedSession.mode = button.dataset.mode || selectedSession.mode;
  hideContextMenu();
  saveState();
  renderApp();
});

sessionList.addEventListener("contextmenu", (event) => {
  const button = event.target.closest("[data-response-id]");
  if (!button) {
    return;
  }
  event.preventDefault();
  pendingDelete = {
    sessionId: button.dataset.sessionId,
    responseId: button.dataset.responseId,
    requestId: button.dataset.requestId
  };
  contextMenu.style.left = `${event.clientX}px`;
  contextMenu.style.top = `${event.clientY}px`;
  contextMenu.hidden = false;
});

document.querySelector("[data-delete-history]").addEventListener("click", () => {
  if (!pendingDelete) {
    return;
  }
  deleteHistoryEntry(pendingDelete);
  pendingDelete = null;
  hideContextMenu();
});

document.addEventListener("click", (event) => {
  if (!contextMenu.hidden && !event.target.closest("[data-context-menu]")) {
    hideContextMenu();
  }
});

composerInput.addEventListener("input", () => {
  composerInput.classList.toggle("has-input", composerInput.innerText.trim().length > 0);
});

document.querySelector("[data-composer]").addEventListener("submit", (event) => {
  event.preventDefault();
  void submitQuery();
});

async function submitQuery() {
  console.log("[submit] start");
  const query = composerInput.innerText.trim();
  if (!query || sendButton.classList.contains("is-loading")) {
    composerInput.classList.toggle("is-empty", !query);
    console.log("[submit] ignored", { hasQuery: Boolean(query), isLoading: sendButton.classList.contains("is-loading") });
    return;
  }

  const session = getActiveSession();
  const mode = session.mode;
  const requestId = createId("request");
  session.messages.push({
    id: createId("message"),
    role: "user",
    content: query,
    mode,
    requestId,
    createdAt: Date.now()
  });
  session.title = query.slice(0, 28);
  session.trace = [];
  session.updatedAt = Date.now();
  saveState();
  renderLoading();

  try {
    console.log("[submit] before queryOnCall", { query, mode });
    const response = await queryOnCall(query, mode);
    console.log("[submit] after queryOnCall", response);
    const activeSession = getActiveSession();
    const responseId = createId("response");
    activeSession.messages.push({
      id: responseId,
      role: "assistant",
      mode,
      answer: response.answer,
      sources: response.sources ?? [],
      trace: [
        ...(response.trace ?? []),
        {
          stage: "frontend",
          event: "frontend_answer_received",
          frontend_answer_chars: String(response.answer || "").length
        }
      ],
      error: "",
      requestId,
      createdAt: Date.now()
    });
    appState.activeResponseId = responseId;
    activeSession.trace = activeSession.messages[activeSession.messages.length - 1].trace;
    activeSession.updatedAt = Date.now();
    composerInput.textContent = "";
    composerInput.classList.remove("has-input", "is-empty");
    saveState();
    renderApp();
  } catch (error) {
    console.log("[submit] error", error);
    const activeSession = getActiveSession();
    const trace = [
      {
        step: 0,
        event: "frontend_error",
        detail: error instanceof Error ? error.message : "unknown request error"
      }
    ];
    activeSession.messages.push({
      id: createId("response"),
      role: "assistant",
      mode,
      answer: "",
      sources: [],
      trace,
      error: error instanceof Error ? error.message : "Request failed.",
      requestId,
      createdAt: Date.now()
    });
    appState.activeResponseId = activeSession.messages[activeSession.messages.length - 1].id;
    activeSession.trace = trace;
    activeSession.updatedAt = Date.now();
    saveState();
    renderApp();
  } finally {
    console.log("[submit] finally");
    clearLoadingState();
  }
}

renderApp();

function loadState() {
  try {
    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "null");
    if (stored?.sessions?.length && stored.activeSessionId) {
      normalizeStoredState(stored);
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
    trace: [],
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
  const selectedAnswer = getSelectedAnswer();
  if (appState.activeResponseId && selectedAnswer?.message.mode) {
    session.mode = selectedAnswer.message.mode;
  }
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
  renderSelectedAnswer(selectedAnswer);
  renderTrace(selectedAnswer?.message.trace ?? session.trace);
  renderHistoryVisibility();
}

function renderHistoryVisibility() {
  document.querySelector(".history-panel").classList.toggle("is-open", isHistoryOpen);
  document.querySelector(".history-rail").classList.toggle("is-hidden", isHistoryOpen);
}

function renderSessions() {
  const entries = getHistoryEntries();
  if (!entries.length) {
    sessionList.innerHTML = `<p class="history-empty">No answer history yet.</p>`;
    return;
  }

  sessionList.innerHTML = entries
    .map(
      (entry) => `
        <button
          type="button"
          data-session-id="${entry.sessionId}"
          data-response-id="${entry.responseId}"
          data-request-id="${entry.requestId}"
          data-mode="${entry.mode}"
          class="${entry.responseId === appState.activeResponseId ? "is-active" : ""}"
        >
          <strong>${escapeHtml(entry.title)}</strong>
          <span>${escapeHtml(entry.mode)} · ${escapeHtml(entry.summary)}</span>
        </button>
      `
    )
    .join("");
}

function renderSelectedAnswer(selectedAnswer) {
  const session = getActiveSession();
  if (!selectedAnswer) {
    answerSurface.innerHTML = `
      <div class="empty-state">
        <p>${modeAssets[session.mode].label} mode selected.</p>
        <span>Submit a query to request the backend.</span>
      </div>
    `;
    return;
  }

  answerSurface.innerHTML = renderAnswerPanel(selectedAnswer.message, selectedAnswer.title);
}

function renderLoading() {
  sendButton.classList.add("is-loading");
  sendButton.setAttribute("aria-busy", "true");
  answerSurface.querySelectorAll("[data-loading-message]").forEach((node) => node.remove());
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

function clearLoadingState() {
  sendButton.classList.remove("is-loading");
  sendButton.removeAttribute("aria-busy");
  answerSurface.querySelectorAll("[data-loading-message]").forEach((node) => node.remove());
}

function renderAnswerPanel(session, question = "") {
  return `
    <article class="answer-panel">
      <span class="response-badge">${escapeHtml(session.mode)} response</span>
      <div class="question-box">
        <span>${escapeHtml(question || "Untitled question")}</span>
      </div>
      <h2>Answer</h2>
      ${
        session.error
          ? `<p class="message-error">${escapeHtml(session.error)}</p>`
          : `<p class="answer-text">${escapeHtml(session.answer || "")}</p>`
      }
      ${renderSources(session.sources ?? [])}
      ${renderDebugPanel(session)}
    </article>
  `;
}

function renderSources(sources) {
  const rows = sources
    .map((source) => {
      return `
        <li>
          <div class="source-main">
            <strong>${escapeHtml(source.id || source.filename || "source")}</strong>
            <span>${escapeHtml(source.title || "No source title")}</span>
            ${source.score ? `<b>score: ${escapeHtml(source.score)}</b>` : ""}
          </div>
          <details class="source-original">
            <summary>Read source excerpt</summary>
            <pre>${escapeHtml(source.snippet || "No source excerpt returned by backend.")}</pre>
          </details>
        </li>
      `;
    })
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

function getSelectedAnswer() {
  if (!appState.activeResponseId) {
    return null;
  }

  const entries = getHistoryEntries();
  if (!entries.length) {
    appState.activeResponseId = "";
    return null;
  }

  let entry = entries.find((item) => item.responseId === appState.activeResponseId);
  if (!entry) {
    appState.activeResponseId = "";
    return null;
  }
  return entry;
}

function getHistoryEntries() {
  return appState.sessions
    .flatMap((session) =>
      session.messages
        .filter((message) => message.role === "assistant")
        .map((message) => {
          const queryMessage = findRequestQuery(session.messages, message);
          return {
            sessionId: session.id,
            responseId: message.id,
            requestId: message.requestId || "",
            mode: message.mode || session.mode,
            title: queryMessage?.content || session.title || "Untitled",
            summary: message.error || message.answer || "No answer text",
            createdAt: message.createdAt || session.updatedAt,
            message
          };
        })
    )
    .sort((left, right) => right.createdAt - left.createdAt);
}

function findRequestQuery(messages, response) {
  if (response.requestId) {
    const match = messages.find((message) => message.role === "user" && message.requestId === response.requestId);
    if (match) {
      return match;
    }
  }

  const responseIndex = messages.findIndex((message) => message.id === response.id);
  for (let index = responseIndex - 1; index >= 0; index -= 1) {
    if (messages[index].role === "user") {
      return messages[index];
    }
  }
  return null;
}

function deleteHistoryEntry(entry) {
  const session = appState.sessions.find((item) => item.id === entry.sessionId);
  if (!session) {
    return;
  }

  if (entry.requestId) {
    session.messages = session.messages.filter((message) => message.requestId !== entry.requestId);
  } else {
    session.messages = session.messages.filter((message) => message.id !== entry.responseId);
  }

  if (appState.activeResponseId === entry.responseId) {
    appState.activeResponseId = "";
  }
  session.updatedAt = Date.now();
  saveState();
  renderApp();
}

function normalizeStoredState(state) {
  state.activeResponseId = state.activeResponseId || "";
  state.sessions.forEach((session) => {
    session.messages = Array.isArray(session.messages) ? session.messages : [];
    session.messages.forEach((message) => {
      message.id = message.id || createId(message.role === "assistant" ? "response" : "message");
      message.requestId = message.requestId || createId("request");
    });
  });
}

function hideContextMenu() {
  contextMenu.hidden = true;
}

function createId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
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
          <p>${escapeHtml(JSON.stringify(item, null, 2))}</p>
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
