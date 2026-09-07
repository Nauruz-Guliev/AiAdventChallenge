const taskElement = document.getElementById('task');
const cardsElement = document.getElementById('cards');
const statusElement = document.getElementById('status');
const runAllButton = document.getElementById('run-all');

let task = '';
let models = [];
const results = {};
const running = new Set();

function addText(parent, text, className = '') {
  const node = document.createElement('div');
  node.className = className;
  node.textContent = text;
  parent.appendChild(node);
  return node;
}

function setStatus(message = '', retryAction = null) {
  statusElement.replaceChildren();
  if (message) {
    addText(statusElement, message);
    if (retryAction) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = 'Повторить';
      button.addEventListener('click', retryAction);
      statusElement.appendChild(button);
    }
  }
  statusElement.classList.toggle('visible', Boolean(message));
}

function friendlyError(error) {
  const message = String(error?.message || '');
  if (/failed to fetch|connection|network|econn|enotfound|eai_again/iu.test(message)) {
    return 'Не удалось подключиться к локальному серверу. Проверьте, что npm start запущен, и повторите попытку.';
  }
  return message || 'Неизвестная ошибка. Повторите попытку.';
}

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchJson(url, options = {}, retries = 0) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const response = await fetch(url, options);
      const data = await response.json().catch(() => ({}));
      if (response.ok) return data;
      lastError = new Error(data.error || `Сервер вернул статус ${response.status}.`);
      if (attempt < retries && [502, 503, 504].includes(response.status)) {
        await wait(700 * (attempt + 1));
        continue;
      }
      throw lastError;
    } catch (error) {
      lastError = error;
      if (attempt < retries) {
        await wait(700 * (attempt + 1));
        continue;
      }
    }
  }
  throw new Error(friendlyError(lastError));
}

function inlineMarkdown(text) {
  return text
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/_([^_]+)_/g, '<em>$1</em>');
}

function markdownToHtml(source) {
  const escaped = source.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const output = [];
  let listType = '';
  const closeList = () => {
    if (listType) output.push(`</${listType}>`);
    listType = '';
  };
  escaped.split('\n').forEach(line => {
    if (!line.trim()) { closeList(); return; }
    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (ordered) {
      if (listType !== 'ol') { closeList(); listType = 'ol'; output.push('<ol>'); }
      output.push(`<li>${inlineMarkdown(ordered[1])}</li>`);
      return;
    }
    closeList();
    const heading = line.match(/^#{1,3}\s+(.+)$/);
    output.push(heading ? `<h4>${inlineMarkdown(heading[1])}</h4>` : `<p>${inlineMarkdown(line)}</p>`);
  });
  closeList();
  return output.join('');
}

function metric(label, value, suffix = '') {
  const item = document.createElement('div');
  item.className = 'metric';
  addText(item, label, 'metric-label');
  addText(item, value == null ? '—' : `${value}${suffix}`, 'metric-value');
  return item;
}

function placeholder(model) {
  return { text: '', usage: {}, evaluation: { rubricScore: null } };
}

function renderCards() {
  cardsElement.replaceChildren();
  models.forEach((model, index) => {
    const result = results[model.id] || placeholder(model);
    const card = document.createElement('article');
    card.className = `model-card ${model.tier}`;
    const top = document.createElement('div');
    top.className = 'card-top';
    addText(top, `0${index + 1}`, 'card-number');
    addText(top, model.label, 'tier');
    card.appendChild(top);
    addText(card, model.hfModel, 'model-name');
    addText(card, model.description, 'model-description');

    const price = document.createElement('div');
    price.className = 'price';
    addText(price, `$${model.inputPrice.toFixed(2)} / $${model.outputPrice.toFixed(2)}`, 'price-value');
    addText(price, 'input / output за 1M токенов', 'price-label');
    card.appendChild(price);

    const button = document.createElement('button');
    button.className = 'run-button';
    button.disabled = running.has(model.id);
    button.textContent = running.has(model.id) ? 'Модель отвечает...' : `Запустить ${model.label.toLowerCase()}`;
    button.addEventListener('click', () => runModel(model));
    card.appendChild(button);

    const answer = document.createElement('div');
    answer.className = `answer${result.text ? '' : ' empty'}`;
    if (result.text) answer.innerHTML = markdownToHtml(result.text);
    else answer.textContent = result.error
      ? result.error
      : result.finishReason === 'length'
        ? 'Ответ не вернулся: модель исчерпала лимит генерации до появления видимого текста.'
        : 'Ответ появится после запуска модели.';
    card.appendChild(answer);

    const metrics = document.createElement('div');
    metrics.className = 'metrics';
    metrics.append(
      metric('Качество · rubric', result.evaluation.rubricScore, '%'),
      metric('Время', result.latencyMs == null ? null : (result.latencyMs / 1000).toFixed(1), ' с'),
      metric('Токены', result.usage.totalTokens),
      metric('Цена', result.estimatedCostUsd == null ? null : `$${result.estimatedCostUsd.toFixed(4)}`),
    );
    card.appendChild(metrics);

    const signals = result.evaluation.signals;
    const stats = result.error
      ? `Ошибка · ${result.error}`
      : result.text || result.finishReason
      ? `Вход ${result.usage.promptTokens ?? '—'} · выход ${result.usage.completionTokens ?? '—'} · ${result.finishReason} · ${signals ? Object.values(signals).filter(Boolean).length : 0}/5 сигналов`
      : 'Вызов ещё не запускался';
    addText(card, stats, 'stats');
    const link = document.createElement('a');
    link.href = model.sourceUrl;
    link.target = '_blank';
    link.rel = 'noreferrer';
    link.textContent = `${model.sourceLabel || 'Карточка Hugging Face'} ↗`;
    link.className = 'source-link';
    card.appendChild(link);
    cardsElement.appendChild(card);
  });
  runAllButton.disabled = running.size > 0;
}

async function poll(runId, model) {
  const data = await fetchJson(`/api/run/${runId}`, {}, 2);
  if (data.state === 'running') {
    setStatus(`${model.label}: модель отвечает...`);
    await new Promise(resolve => setTimeout(resolve, 700));
    return poll(runId, model);
  }
  if (data.state === 'complete') return data.result;
  throw new Error(data.error || 'Запрос завершился с ошибкой.');
}

async function runModel(model) {
  running.add(model.id);
  setStatus('');
  renderCards();
  try {
    const data = await fetchJson('/api/run-model', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: model.id, prompt: task }),
    });
    results[model.id] = await poll(data.runId, model);
  } catch (error) {
    const message = friendlyError(error);
    setStatus(message, () => runModel(model));
    results[model.id] = {
      text: '',
      error: message,
      usage: {},
      evaluation: { rubricScore: 0, signals: {} },
    };
  } finally {
    running.delete(model.id);
    renderCards();
  }
}

runAllButton.addEventListener('click', () => Promise.all(models.map(runModel)));

async function loadConfig() {
  const config = await fetchJson('/api/config', {}, 3);
  task = config.task;
  models = config.models;
  taskElement.textContent = task;
  renderCards();
}

loadConfig().catch(error => setStatus(friendlyError(error), loadConfig));
