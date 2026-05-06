const form = document.querySelector("#research-form");
const questionInput = document.querySelector("#question-input");
const runButton = document.querySelector("#run-button");
const clearButton = document.querySelector("#clear-button");
const sampleButton = document.querySelector("#sample-button");
const statusStrip = document.querySelector("#status-strip");
const statusText = document.querySelector("#status-text");
const emptyState = document.querySelector("#empty-state");
const resultContent = document.querySelector("#result-content");
const resultTitle = document.querySelector("#result-title");
const summaryText = document.querySelector("#summary-text");
const findingsList = document.querySelector("#findings-list");
const sourcesList = document.querySelector("#sources-list");
const queriesList = document.querySelector("#queries-list");
const entitiesList = document.querySelector("#entities-list");
const metrics = document.querySelector("#metrics");
const historyList = document.querySelector("#history-list");
const refreshHistoryButton = document.querySelector("#refresh-history-button");
const sessionLookupForm = document.querySelector("#session-lookup-form");
const sessionIdInput = document.querySelector("#session-id-input");
const copySessionButton = document.querySelector("#copy-session-button");

const samples = [
  "Who is Andrej Karpathy?",
  "Who is Sam Altman?",
  "What is OpenClaw and what is it used for?",
  "What are practical approaches to RAG evaluation?",
  "Compare Tavily, Exa, and Brave Search for AI research agents",
];

let activeSessionId = "";
let sampleIndex = 0;

function setLoading(isLoading, message = "Planning search strategy...") {
  runButton.disabled = isLoading;
  refreshHistoryButton.disabled = isLoading;
  statusText.textContent = message;
  statusStrip.hidden = !isLoading;
}

function showError(message) {
  emptyState.hidden = true;
  resultContent.hidden = false;
  resultTitle.textContent = "Something needs attention";
  metrics.innerHTML = "";
  summaryText.innerHTML = "";
  findingsList.innerHTML = "";
  sourcesList.innerHTML = "";
  queriesList.innerHTML = "";
  entitiesList.innerHTML = "";

  const errorBox = document.createElement("div");
  errorBox.className = "error-box";
  errorBox.textContent = message;
  summaryText.replaceChildren(errorBox);
}

function formatSeconds(value) {
  if (!Number.isFinite(Number(value))) {
    return "0.0s";
  }
  return `${Number(value).toFixed(1)}s`;
}

function addMetric(label, value) {
  const item = document.createElement("span");
  item.className = "metric";
  item.textContent = `${label}: ${value}`;
  metrics.appendChild(item);
}

function renderList(target, items, fallback) {
  target.innerHTML = "";
  const values = Array.isArray(items) && items.length ? items : [fallback];
  values.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    target.appendChild(li);
  });
}

function renderSources(sources) {
  sourcesList.innerHTML = "";
  if (!Array.isArray(sources) || sources.length === 0) {
    const empty = document.createElement("p");
    empty.className = "source-insight";
    empty.textContent = "No sources were returned for this session.";
    sourcesList.appendChild(empty);
    return;
  }

  sources.forEach((source) => {
    const item = document.createElement("article");
    item.className = "source-item";

    const titleRow = document.createElement("div");
    titleRow.className = "source-title";

    const link = document.createElement("a");
    link.href = source.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = source.title || source.url;
    titleRow.appendChild(link);

    if (source.source_type) {
      const type = document.createElement("span");
      type.className = "source-type";
      type.textContent = source.source_type;
      titleRow.appendChild(type);
    }

    const insight = document.createElement("p");
    insight.className = "source-insight";
    insight.textContent = source.insight || source.url;

    item.append(titleRow, insight);
    sourcesList.appendChild(item);
  });
}

function renderResult(data) {
  activeSessionId = data.session_id || "";
  emptyState.hidden = true;
  resultContent.hidden = false;
  resultTitle.textContent = data.question || "Research result";
  summaryText.textContent = data.summary || "No summary returned.";

  metrics.innerHTML = "";
  addMetric("Session", activeSessionId ? activeSessionId.slice(0, 8) : "none");
  addMetric("Web", data.web_count ?? 0);
  addMetric("arXiv", data.arxiv_count ?? 0);
  addMetric("Duration", formatSeconds(data.duration_seconds));

  renderList(findingsList, data.key_findings, "No key findings returned.");
  renderSources(data.sources);
  renderList(queriesList, data.search_queries, "No search queries recorded.");
  renderList(entitiesList, data.core_entities, "No core entities recorded.");

  if (Array.isArray(data.tool_errors) && data.tool_errors.length > 0) {
    addMetric("Tool errors", data.tool_errors.length);
  }
}

function renderHistory(items) {
  historyList.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    const empty = document.createElement("p");
    empty.className = "source-insight";
    empty.textContent = "No saved sessions yet.";
    historyList.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const button = document.createElement("button");
    button.className = "history-item";
    button.type = "button";

    const question = document.createElement("p");
    question.className = "history-question";
    question.textContent = item.question;

    const meta = document.createElement("div");
    meta.className = "history-meta";
    meta.textContent = `${formatSeconds(item.duration_seconds)} | ${item.web_count} web | ${
      item.arxiv_count
    } arXiv`;

    button.append(question, meta);
    button.addEventListener("click", () => loadSession(item.session_id));
    historyList.appendChild(button);
  });
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = data && data.detail ? data.detail : response.statusText;
    throw new Error(detail);
  }
  return data;
}

async function loadHistory() {
  const sessions = await requestJson("/sessions?limit=12");
  renderHistory(sessions);
}

async function loadSession(sessionId) {
  if (!sessionId) {
    showError("Paste a valid session ID first.");
    return;
  }
  setLoading(true, "Loading saved session...");
  try {
    const session = await requestJson(`/sessions/${encodeURIComponent(sessionId)}`);
    renderResult(session);
  } catch (error) {
    showError(error.message);
  } finally {
    setLoading(false);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) {
    questionInput.focus();
    return;
  }

  setLoading(true, "Researching. This can take 20-60 seconds...");
  try {
    const result = await requestJson("/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    renderResult(result);
    await loadHistory();
  } catch (error) {
    showError(error.message);
  } finally {
    setLoading(false);
  }
});

clearButton.addEventListener("click", () => {
  questionInput.value = "";
  questionInput.focus();
});

sampleButton.addEventListener("click", () => {
  questionInput.value = samples[sampleIndex % samples.length];
  sampleIndex += 1;
  questionInput.focus();
});

refreshHistoryButton.addEventListener("click", async () => {
  setLoading(true, "Refreshing history...");
  try {
    await loadHistory();
  } catch (error) {
    showError(error.message);
  } finally {
    setLoading(false);
  }
});

sessionLookupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await loadSession(sessionIdInput.value.trim());
});

copySessionButton.addEventListener("click", async () => {
  if (!activeSessionId) {
    return;
  }
  await navigator.clipboard.writeText(activeSessionId);
  copySessionButton.textContent = "Copied";
  window.setTimeout(() => {
    copySessionButton.textContent = "Copy session ID";
  }, 1200);
});

loadHistory().catch((error) => showError(error.message));
