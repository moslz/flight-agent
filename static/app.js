const chatWindow = document.getElementById("chat-window");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const newChatBtn = document.getElementById("new-chat-btn");

const welcomeHTML = chatWindow.innerHTML;

let threadId = getOrCreateThreadId();
loadHistory();

if (newChatBtn) {
  newChatBtn.addEventListener("click", startNewConversation);
} else {
  console.warn('New chat button not found (expected an element with id="new-chat-btn") — skipping.');
}

function startNewConversation() {
  threadId = crypto.randomUUID();
  localStorage.setItem("flight-agent-thread-id", threadId);
  chatWindow.innerHTML = welcomeHTML;
  userInput.focus();
}

function getOrCreateThreadId() {
  let id = localStorage.getItem("flight-agent-thread-id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("flight-agent-thread-id", id);
  }
  return id;
}

async function loadHistory() {
  try {
    const response = await fetch(`/history/${threadId}`);
    const data = await response.json();
    if (data.messages && data.messages.length > 0) {
      document.getElementById("welcome")?.remove();
      for (const msg of data.messages) {
        appendMessage(msg.role, msg.content);
      }
    }
    if (data.pending_interrupt) {
      setInputEnabled(false);
      renderInterrupt(data.pending_interrupt);
    }
  } catch {
  }
}

userInput.addEventListener("input", () => {
  userInput.style.height = "auto";
  userInput.style.height = `${userInput.scrollHeight}px`;
});

userInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener("click", sendMessage);

async function sendMessage() {
  const text = userInput.value.trim();
  if (!text) return;

  userInput.value = "";
  userInput.style.height = "auto";
  setInputEnabled(false);

  appendMessage("user", text);

  const typing = showTyping();

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thread_id: threadId, message: text }),
    });
    const data = await response.json();
    typing.remove();
    handleAgentResponse(data);
  } catch {
    typing.remove();
    appendMessage("agent", "Could not reach the server.");
    setInputEnabled(true);
    userInput.focus();
  }
}

function handleAgentResponse(data) {
  if (data.status === "success") {
    appendMessage("agent", data.message);
    setInputEnabled(true);
    userInput.focus();
  } else if (data.status === "interrupt") {
    renderInterrupt(data.interrupt);
  } else {
    appendMessage("agent", `Something went wrong: ${data.message}`);
    setInputEnabled(true);
    userInput.focus();
  }
}

function renderInterrupt(interrupt) {
  if (interrupt.type === "search_tool_choice") {
    renderSearchToolChoice(interrupt);
  } else if (interrupt.type === "booking_confirmation") {
    renderBookingConfirmation(interrupt);
  } else {
    appendMessage("agent", "I need a decision to continue, but don't recognize this prompt type. Try rephrasing your request.");
    setInputEnabled(true);
  }
}

function renderSearchToolChoice(interrupt) {
  const q = interrupt.query || {};
  const routeLabel = `${q.origin || "?"} → ${q.destination || "?"}${q.outbound_date ? " on " + q.outbound_date : ""}`;

  const card = buildChoiceCard(`Which search should I use for ${routeLabel}?`);
  const tools = interrupt.tools || {};

  for (const [key, info] of Object.entries(tools)) {
    const btn = document.createElement("button");
    btn.className = "choice-btn";
    btn.innerHTML = `<span class="choice-btn-label">${escapeHTML(info.label)}</span><span class="choice-btn-desc">${escapeHTML(info.description)}</span>`;
    btn.addEventListener("click", () => {
      disableChoiceCard(card);
      sendResume({ tool: key });
    });
    card.appendChild(btn);
  }

  appendCard(card);
}

function renderBookingConfirmation(interrupt) {
  const f = interrupt.flight || {};
  const summary = f.airline
    ? `${f.airline} ${f.flight_number || ""} — EUR ${f.price ?? "?"} — ${f.stops === 0 ? "nonstop" : `${f.stops} stop(s)`}`.trim()
    : "this flight";

  const card = buildChoiceCard(`Look up real booking links for ${summary}?`);

  const row = document.createElement("div");
  row.className = "choice-btn-row";

  const yes = document.createElement("button");
  yes.className = "choice-btn choice-btn-confirm";
  yes.textContent = "Yes, get booking links";
  yes.addEventListener("click", () => {
    disableChoiceCard(card);
    sendResume({ confirmed: true });
  });

  const no = document.createElement("button");
  no.className = "choice-btn choice-btn-cancel";
  no.textContent = "Cancel";
  no.addEventListener("click", () => {
    disableChoiceCard(card);
    sendResume({ confirmed: false });
  });

  row.appendChild(yes);
  row.appendChild(no);
  card.appendChild(row);

  appendCard(card);
}

function buildChoiceCard(titleText) {
  const card = document.createElement("div");
  card.className = "choice-card";

  const title = document.createElement("div");
  title.className = "choice-card-title";
  title.textContent = titleText;
  card.appendChild(title);

  return card;
}

function appendCard(card) {
  const wrapper = document.createElement("div");
  wrapper.className = "message agent-message";
  wrapper.appendChild(card);
  chatWindow.appendChild(wrapper);
  wrapper.scrollIntoView({ behavior: "smooth", block: "end" });
}

function disableChoiceCard(card) {
  card.querySelectorAll("button").forEach((b) => (b.disabled = true));
}

function escapeHTML(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

async function sendResume(payload) {
  const typing = showTyping();
  try {
    const response = await fetch("/resume", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thread_id: threadId, payload }),
    });
    const data = await response.json();
    typing.remove();
    handleAgentResponse(data);
  } catch {
    typing.remove();
    appendMessage("agent", "Could not reach the server.");
    setInputEnabled(true);
    userInput.focus();
  }
}

function appendMessage(role, text) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role === "user" ? "user-message" : "agent-message"}`;

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.innerHTML = formatText(text);

  wrapper.appendChild(bubble);
  chatWindow.appendChild(wrapper);
  wrapper.scrollIntoView({ behavior: "smooth", block: "end" });
}

function showTyping() {
  const wrapper = document.createElement("div");
  wrapper.className = "message agent-message";

  const indicator = document.createElement("div");
  indicator.className = "typing-indicator";
  indicator.innerHTML = "<span></span><span></span><span></span>";

  wrapper.appendChild(indicator);
  chatWindow.appendChild(wrapper);
  wrapper.scrollIntoView({ behavior: "smooth", block: "end" });
  return wrapper;
}

function setInputEnabled(enabled) {
  userInput.disabled = !enabled;
  sendBtn.disabled = !enabled;
}

function formatText(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/https?:\/\/[^\s<]+/g, (match) => {
      const trailing = match.match(/[).,;:!?\]]+$/);
      const url = trailing ? match.slice(0, -trailing[0].length) : match;
      const suffix = trailing ? trailing[0] : "";
      return `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>${suffix}`;
    })
    .replace(/\n/g, "<br>");
}