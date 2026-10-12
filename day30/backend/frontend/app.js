const $ = (id) => document.getElementById(id);
const keyInput = $("key");
const modelSelect = $("model");
const messages = $("messages");
const limits = $("limits");
const health = $("health");

let history = [];

keyInput.value = localStorage.getItem("llm_api_key") || "";
keyInput.addEventListener("change", () => {
  localStorage.setItem("llm_api_key", keyInput.value.trim());
  refreshModels();
  refreshLimits();
});

function headers() {
  return { "Content-Type": "application/json", "X-API-Key": keyInput.value.trim() };
}

function bubble(role, text) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  el.textContent = text;
  messages.appendChild(el);
  messages.scrollTop = messages.scrollHeight;
  return el;
}

function showLimits(data) {
  limits.innerHTML = Object.entries(data)
    .map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`)
    .join("");
}

async function refreshHealth() {
  try {
    const response = await fetch("/health");
    const data = await response.json();
    health.textContent = data.status === "ok" ? "Ollama: ok" : "Ollama: degraded";
    health.className = `badge ${data.status === "ok" ? "ok" : "bad"}`;
  } catch {
    health.textContent = "сервис недоступен";
    health.className = "badge bad";
  }
}

async function refreshModels() {
  try {
    const response = await fetch("/v1/models", { headers: headers() });
    if (!response.ok) return;
    const data = await response.json();
    modelSelect.innerHTML = data.data.map((m) => `<option>${m.id}</option>`).join("");
  } catch {}
}

async function refreshLimits() {
  try {
    const response = await fetch("/metrics", { headers: headers() });
    if (response.ok) showLimits(await response.json());
  } catch {}
}

async function send(prompt) {
  history.push({ role: "user", content: prompt });
  bubble("user", prompt);
  const target = bubble("assistant", "…");
  const response = await fetch("/v1/chat/completions", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ model: modelSelect.value, messages: history, stream: true }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: { message: response.statusText } }));
    target.className = "msg error";
    target.textContent = `${response.status}: ${error.error.message}`;
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let answer = "";
  target.textContent = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop();
    for (const part of parts) {
      if (!part.startsWith("data: ")) continue;
      const payload = part.slice(6);
      if (payload === "[DONE]") continue;
      const chunk = JSON.parse(payload);
      answer += chunk.choices[0].delta.content || "";
      target.textContent = answer;
      messages.scrollTop = messages.scrollHeight;
    }
  }
  history.push({ role: "assistant", content: answer });
  refreshLimits();
}

$("composer").addEventListener("submit", (event) => {
  event.preventDefault();
  const prompt = $("prompt").value.trim();
  if (!prompt) return;
  $("prompt").value = "";
  send(prompt);
});

$("clear").addEventListener("click", () => {
  history = [];
  messages.innerHTML = "";
});

refreshHealth();
refreshModels();
refreshLimits();
setInterval(refreshHealth, 10000);
