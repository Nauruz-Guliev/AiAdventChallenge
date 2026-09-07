const taskElement = document.getElementById('task');
const methodsElement = document.getElementById('methods');
const statusElement = document.getElementById('status');
const runState = document.getElementById('run-state');
const modelElement = document.getElementById('model');
const stages = document.getElementById('stages');

let task = '';
let generatedPrompt = '';
let activeMethod = '';
const results = {};

const labels = {
  direct: 'Прямой ответ',
  step: 'Пошаговое решение',
  generated: 'Сгенерированный промпт',
  experts: 'Группа экспертов',
};

const descriptions = {
  direct: 'Только исходная задача. Никаких дополнительных инструкций.',
  step: 'К задаче добавлен отдельный system prompt с просьбой рассуждать пошагово.',
  generated: 'Сначала формируется system prompt, затем автоматически выполняется запрос с ним.',
  experts: 'Один system prompt создаёт аналитика, инженера, критика и координатора.',
};

const differences = {
  direct: 'system отсутствует. В messages используется только user: [ЗАДАЧА].',
  step: 'system:\n«Решай задачу пошагово: перечисли условия, проверь варианты и объясни вывод. В конце обязательно дай краткий ответ, даже если внутреннее рассуждение было длинным.»',
  generated: 'system:\n[СЮДА БУДЕТ ВСТАВЛЕН СФОРМИРОВАННЫЙ SYSTEM PROMPT]',
  experts: 'system:\n«Работай как группа из трёх экспертов. Аналитик выделит физические признаки выхода. Инженер составит безопасный порядок проверки. Критик попробует найти ошибку или опасный шаг. Пусть каждый эксперт сначала даст свой вывод, а затем координатор сравнит их и сформулирует итоговый ответ. В конце обязательно дай краткий итог.»',
};

function addText(parent, text, className = '') {
  const node = document.createElement('div');
  node.className = className;
  node.textContent = text;
  parent.appendChild(node);
  return node;
}

function stat(label, value) {
  const node = document.createElement('span');
  node.className = 'stat';
  node.textContent = `${label}: ${value == null ? 'нет данных' : value}`;
  return node;
}

function setStage(index) {
  stages.querySelectorAll('.stage').forEach((item, itemIndex) => {
    item.classList.toggle('active', itemIndex === index);
    item.classList.toggle('done', itemIndex < index);
  });
}

function setStatus(message) {
  statusElement.textContent = message;
  statusElement.classList.toggle('visible', Boolean(message));
}

function placeholderMethod(key) {
  return {
    key,
    title: labels[key],
    description: descriptions[key],
    text: '',
    evaluation: { exact: false, score: 0, status: 'Ожидает запуска', judgeReason: '' },
    usage: {},
    finishReason: null,
  };
}

function renderCards() {
  methodsElement.replaceChildren();
  ['direct', 'step', 'generated', 'experts'].forEach((key, index) => {
    const method = results[key] || placeholderMethod(key);
    const article = document.createElement('article');
    article.className = `method ${method.evaluation.exact ? 'exact' : ''}`;

    const top = document.createElement('div');
    top.className = 'method-top';
    addText(top, `0${index + 1}`, 'method-number');
    addText(top, labels[key], 'method-title');
    article.appendChild(top);
    addText(article, descriptions[key], 'method-description');

    const difference = document.createElement('div');
    difference.className = `difference${key === 'generated' ? ' generated-difference' : ''}`;
    addText(difference, 'SYSTEM PROMPT / ОТЛИЧИЕ', 'difference-label');
    addText(difference, key === 'generated' && generatedPrompt ? generatedPrompt : differences[key]);
    article.appendChild(difference);

    const button = document.createElement('button');
    button.className = `method-action${key === 'generated' && generatedPrompt ? ' ready' : ''}`;
    button.disabled = Boolean(activeMethod);
    if (activeMethod === key) {
      button.textContent = key === 'generated' && !generatedPrompt ? 'Формируем промпт...' : 'Выполняется...';
    } else if (key === 'generated') {
      button.textContent = 'Сформировать промпт и запустить';
    } else {
      button.textContent = `Запустить ${labels[key].toLocaleLowerCase('ru-RU')}`;
    }
    button.addEventListener('click', () => key === 'generated' ? makePrompt() : runMethod(key));
    article.appendChild(button);

    const answer = document.createElement('pre');
    answer.className = `answer${method.text ? '' : ' empty'}${method.error ? ' error-answer' : ''}`;
    answer.textContent = method.error || method.text || 'Ответ появится после запуска этого варианта.';
    article.appendChild(answer);

    const evaluation = document.createElement('div');
    evaluation.className = 'evaluation';
    const evaluationText = document.createElement('div');
    addText(evaluationText, method.evaluation.status, 'evaluation-title');
    addText(evaluationText, method.evaluation.judgeReason || 'Проверку ответа можно выполнить самостоятельно.', 'evaluation-reason');
    const score = document.createElement('div');
    score.className = 'score';
    score.textContent = method.text ? `${method.evaluation.score}%` : '—';
    evaluation.append(evaluationText, score);
    article.appendChild(evaluation);

    const stats = document.createElement('div');
    stats.className = 'stats';
    stats.append(
      stat('Вход', method.usage?.promptTokens),
      stat('Выход', method.usage?.completionTokens),
      stat('Всего', method.usage?.totalTokens),
      stat('Reasoning', method.usage?.reasoningTokens),
      stat('Время', method.latencyMs ? `${(method.latencyMs / 1000).toFixed(1)} с` : null),
      stat('finish', method.finishReason),
    );
    article.appendChild(stats);
    methodsElement.appendChild(article);
  });
}

async function pollJob(runId, onComplete) {
  const response = await fetch(`/api/run/${runId}`);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Запуск не найден.');
  const seconds = Math.round((data.elapsedMs || 0) / 1000);
  runState.textContent = data.state === 'running' ? `DeepSeek отвечает · ${seconds} с` : 'Ответ получен';
  if (data.state === 'running') {
    return new Promise((resolve, reject) => setTimeout(() => pollJob(runId, onComplete).then(resolve).catch(reject), 1000));
  }
  if (data.state === 'complete') return onComplete(data.result);
  throw new Error(data.error || 'Запрос завершился с ошибкой.');
}

async function runMethod(key) {
  activeMethod = key;
  setStatus('');
  setStage(1);
  renderCards();
  try {
    const response = await fetch('/api/run-method', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ method: key, prompt: task }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Не удалось запустить вариант.');
    await pollJob(data.runId, result => {
      results[key] = result.method;
      setStage(2);
    });
    runState.textContent = `${labels[key]} завершён`;
  } catch (error) {
    setStatus(error.message);
    runState.textContent = 'Ошибка запуска';
  } finally {
    activeMethod = '';
    renderCards();
  }
}

async function makePrompt() {
  activeMethod = 'generated';
  setStatus('');
  setStage(1);
  renderCards();
  try {
    const response = await fetch('/api/generate-prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: task }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Не удалось сформировать промпт.');
    const promptResult = await pollJob(data.runId, result => result);
    generatedPrompt = promptResult.prompt;
    activeMethod = '';
    renderCards();
    await runMethod('generated');
  } catch (error) {
    activeMethod = '';
    setStatus(error.message);
    runState.textContent = 'Ошибка запуска';
    renderCards();
  }
}

async function loadConfig() {
  const response = await fetch('/api/config');
  if (!response.ok) throw new Error('Не удалось загрузить конфигурацию.');
  const config = await response.json();
  task = config.task;
  taskElement.textContent = task;
  modelElement.textContent = config.model;
  renderCards();
}

loadConfig().catch(error => setStatus(error.message));
