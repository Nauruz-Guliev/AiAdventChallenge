const taskElement = document.getElementById('task');
const modelElement = document.getElementById('model');
const cardsElement = document.getElementById('cards');
const statusElement = document.getElementById('status');
const summaryElement = document.getElementById('summary');

let task = '';
let temperatures = [];
const results = {};
const running = new Set();

function addText(parent, text, className = '') {
  const node = document.createElement('div');
  node.className = className;
  node.textContent = text;
  parent.appendChild(node);
  return node;
}

function setStatus(message = '') {
  statusElement.textContent = message;
  statusElement.classList.toggle('visible', Boolean(message));
}

function metric(label, value, hint = '') {
  const item = document.createElement('div');
  item.className = 'metric';
  addText(item, label, 'metric-label');
  addText(item, value == null ? '—' : `${value}%`, 'metric-value');
  if (hint) addText(item, hint, 'metric-hint');
  return item;
}

function placeholder(item) {
  return {
    temperature: item.value,
    text: '',
    evaluation: { accuracy: 0, creativity: 0, diversity: 0 },
    usage: {},
  };
}

function renderCards() {
  cardsElement.replaceChildren();
  temperatures.forEach((item, index) => {
    const result = results[item.id] || placeholder(item);
    const card = document.createElement('article');
    card.className = `temperature-card temp-${item.id}`;
    const heading = document.createElement('div');
    heading.className = 'card-heading';
    addText(heading, `0${index + 1}`, 'card-number');
    const title = document.createElement('div');
    addText(title, `temperature = ${item.value}`, 'temperature');
    addText(title, item.label, 'card-title');
    heading.appendChild(title);
    card.appendChild(heading);
    addText(card, item.note, 'card-note');

    const button = document.createElement('button');
    button.className = 'run-card';
    button.disabled = running.has(item.id);
    button.textContent = running.has(item.id) ? 'Модель отвечает...' : `Запустить при ${item.value}`;
    button.addEventListener('click', () => runTemperature(item));
    card.appendChild(button);

    const answer = document.createElement('pre');
    answer.className = `answer${result.text ? '' : ' empty'}`;
    answer.textContent = result.text || 'Ответ появится после запуска этого режима.';
    card.appendChild(answer);

    const metrics = document.createElement('div');
    metrics.className = 'metrics';
    metrics.append(
      metric('Точность формата', result.evaluation.accuracy, 'ограничения'),
      metric('Креативность', result.evaluation.creativity, 'лексический сигнал'),
      metric('Разнообразие', result.evaluation.diversity, 'различие вариантов'),
    );
    card.appendChild(metrics);

    const stats = document.createElement('div');
    stats.className = 'stats';
    stats.textContent = result.text
      ? `Вход ${result.usage.promptTokens ?? '—'} · выход ${result.usage.completionTokens ?? '—'} · ${(result.latencyMs / 1000).toFixed(1)} с · ${result.finishReason}`
      : 'Вызов ещё не запускался';
    card.appendChild(stats);
    cardsElement.appendChild(card);
  });
  renderSummary();
}

function renderSummary() {
  const completed = temperatures.filter(item => results[item.id]);
  summaryElement.replaceChildren();
  if (!completed.length) return;
  const heading = document.createElement('div');
  heading.className = 'summary-heading';
  addText(heading, 'Что наблюдать', 'eyebrow');
  addText(heading, completed.length === temperatures.length ? 'Сравнение завершено' : `Готово ${completed.length} из ${temperatures.length}`, 'summary-title');
  summaryElement.appendChild(heading);
  const list = document.createElement('div');
  list.className = 'summary-list';
  [
    ['temperature = 0', 'Обычно даёт наиболее стабильные и повторяемые ответы. Хорошо для точного формата, классификации и инструкций.'],
    ['temperature = 0.7', 'Часто сохраняет контроль, но добавляет новые формулировки. Универсальный режим для большинства рабочих задач.'],
    ['temperature = 1.2', 'Чаще предлагает неожиданные идеи и разнообразие, но может нарушать ограничения. Полезно для мозгового штурма.'],
  ].forEach(([title, text]) => {
    const item = document.createElement('div');
    item.className = 'summary-item';
    addText(item, title, 'summary-temp');
    addText(item, text, 'summary-text');
    list.appendChild(item);
  });
  summaryElement.appendChild(list);
  addText(summaryElement, 'Метрики на карточках эвристические: они проверяют формат, запретное слово и поверхностное разнообразие текста. Смысловую оценку сравнивайте глазами.', 'summary-footnote');
}

async function poll(runId, item) {
  const response = await fetch(`/api/run/${runId}`);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Запуск не найден.');
  if (data.state === 'running') {
    statusElement.textContent = `temperature = ${item.value}: модель отвечает...`;
    await new Promise(resolve => setTimeout(resolve, 900));
    return poll(runId, item);
  }
  if (data.state === 'complete') return data.result;
  throw new Error(data.error || 'Запрос завершился с ошибкой.');
}

async function runTemperature(item) {
  running.add(item.id);
  setStatus('');
  renderCards();
  try {
    const response = await fetch('/api/run-temperature', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ temperature: item.value, prompt: task }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Не удалось запустить режим.');
    results[item.id] = await poll(data.runId, item);
  } catch (error) {
    setStatus(error.message);
  } finally {
    running.delete(item.id);
    renderCards();
  }
}

async function loadConfig() {
  const response = await fetch('/api/config');
  if (!response.ok) throw new Error('Не удалось загрузить конфигурацию.');
  const config = await response.json();
  task = config.task;
  temperatures = config.temperatures;
  taskElement.textContent = task;
  modelElement.textContent = config.model;
  renderCards();
}

loadConfig().catch(error => setStatus(error.message));
