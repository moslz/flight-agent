const chatWindow = document.getElementById("chat-window");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");

const threadId = getOrCreateThreadId();
loadHistory();

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
  } catch {
    // No history yet, or server unreachable — keep the welcome message.
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

    if (data.status === "success") {
      appendMessage("agent", data.message);
    } else {
      appendMessage("agent", `Something went wrong: ${data.message}`);
    }
  } catch {
    typing.remove();
    appendMessage("agent", "Could not reach the server.");
  }

  setInputEnabled(true);
  userInput.focus();
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
    .replace(/\n/g, "<br>");
}