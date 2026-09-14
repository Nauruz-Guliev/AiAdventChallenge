import { useEffect, useState } from 'react';
import {
  createBranch,
  runCompare,
  createChat,
  deleteBranch,
  deleteChat,
  getChat,
  listChats,
  sendMessage,
  setActiveBranch,
  updateFacts,
} from './api.js';
import AgentFlow from './components/AgentFlow.jsx';
import ChatPanel from './components/ChatPanel.jsx';
import ChatSidebar from './components/ChatSidebar.jsx';
import ComparePanel from './components/ComparePanel.jsx';

const initialStages = [
  { name: 'UI', status: 'completed' },
  { name: 'Agent', status: 'pending' },
  { name: 'DeepSeek API', status: 'pending' },
];

const SIMULATION_FILLER =
  'Опиши очень подробно, как устроен контекст большого диалога, почему история пересылается целиком и как это влияет на токены и стоимость запросов. ';
const SIMULATION_PARTS = 12;

export default function App() {
  const [chats, setChats] = useState([]);
  const [selectedChatId, setSelectedChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [message, setMessage] = useState('');
  const [result, setResult] = useState(null);
  const [stages, setStages] = useState(initialStages);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [dialogUsage, setDialogUsage] = useState(null);
  const [overflow, setOverflow] = useState('');
  const [simulating, setSimulating] = useState(false);
  const [mode, setMode] = useState(
    () => localStorage.getItem('day10-mode') ?? 'sliding'
  );
  const [branches, setBranches] = useState([]);
  const [activeBranchId, setActiveBranchId] = useState(null);
  const [facts, setFacts] = useState({});
  const [comparing, setComparing] = useState(false);
  const [compareRows, setCompareRows] = useState(null);
  const [compareError, setCompareError] = useState('');

  function applyDetail(chat) {
    const chatBranches = chat.branches ?? [];
    setBranches(chatBranches);
    setActiveBranchId(chat.active_branch_id ?? null);
    const active = chatBranches.find(b => b.id === chat.active_branch_id);
    setFacts(active?.facts ?? {});
  }

  useEffect(() => {
    let cancelled = false;

    async function loadInitialChat() {
      try {
        let availableChats = await listChats();
        if (!availableChats.length) {
          const newChat = await createChat();
          availableChats = [newChat];
        }

        if (cancelled) return;
        setChats(availableChats);
        await loadChat(availableChats[0].id, cancelled);
      } catch (requestError) {
        if (!cancelled) setError(requestError.message);
      } finally {
        if (!cancelled) setInitializing(false);
      }
    }

    loadInitialChat();
    async function handleCompare() {
    setComparing(true);
    setCompareError('');
    setCompareRows(null);
    try {
      const results = await runCompare();
      setCompareRows(results);
      setChats(await listChats());
    } catch (requestError) {
      setCompareError(requestError.message);
    } finally {
      setComparing(false);
    }
  }

  async function handleFork(messageIndex) {
    if (!selectedChatId) return;
    try {
      const detail = await createBranch(
        selectedChatId,
        messageIndex + 1,
        `ветка ${branches.length + 1}`
      );
      applyDetail(detail);
      setMessages(detail.messages);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleSwitchBranch(branchId) {
    if (!selectedChatId) return;
    try {
      const detail = await setActiveBranch(selectedChatId, branchId);
      applyDetail(detail);
      setMessages(detail.messages);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleDeleteBranch(branchId) {
    if (!selectedChatId || !window.confirm('Удалить эту ветку со всеми сообщениями?')) return;
    try {
      const detail = await deleteBranch(selectedChatId, branchId);
      applyDetail(detail);
      setMessages(detail.messages);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleFactsChange(nextFacts) {
    if (!selectedChatId) return;
    setFacts(nextFacts);
    try {
      applyDetail(await updateFacts(selectedChatId, nextFacts));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  return () => {
      cancelled = true;
    };
  }, []);

  async function loadChat(chatId, cancelled = false) {
    const chat = await getChat(chatId);
    if (cancelled) return;
    setSelectedChatId(chat.id);
    setMessages(chat.messages);
    setResult(null);
    setError('');
    setStages(initialStages);
    setDialogUsage(chat.dialog_usage);
    setOverflow('');
    applyDetail(chat);
  }

  function handleModeChange(nextMode) {
    setMode(nextMode);
    localStorage.setItem('day10-mode', nextMode);
    setOverflow('');
  }

  async function handleSelectChat(chatId) {
    if (loading || chatId === selectedChatId) return;
    setError('');
    try {
      await loadChat(chatId);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleCreateChat() {
    if (loading || simulating) return;
    setError('');
    try {
      const newChat = await createChat();
      setChats(current => [newChat, ...current]);
      setSelectedChatId(newChat.id);
      setMessages([]);
      setResult(null);
      setStages(initialStages);
      setDialogUsage(null);
      setOverflow('');
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleDeleteChat(chatId) {
    if (loading || !window.confirm('Удалить этот чат и всю его историю?')) return;

    setError('');
    try {
      await deleteChat(chatId);
      const remainingChats = await listChats();
      if (remainingChats.length) {
        setChats(remainingChats);
        if (chatId === selectedChatId) {
          await loadChat(remainingChats[0].id);
        }
        return;
      }

      const newChat = await createChat();
      setChats([newChat]);
      setSelectedChatId(newChat.id);
      setMessages([]);
      setResult(null);
      setStages(initialStages);
      setDialogUsage(null);
      setOverflow('');
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function sendToChat(text) {
    setLoading(true);
    setError('');
    setResult(null);
    setStages([
      { name: 'UI', status: 'completed' },
      { name: 'Agent', status: 'active' },
      { name: 'DeepSeek API', status: 'pending' },
    ]);

    setMessages(current => [...current, { role: 'user', content: text }]);

    try {
      const response = await sendMessage(selectedChatId, text, mode);
      setMessages(current => [
        ...current,
        {
          role: 'assistant',
          content: response.answer,
          usage: {
            request_tokens: response.usage.request_tokens,
            history_tokens: response.usage.history_tokens,
            prompt_tokens: response.usage.prompt_tokens_api,
            completion_tokens: response.usage.completion_tokens_api,
            total_tokens: response.usage.total_tokens_api,
          },
          context: response.usage?.context ?? null,
        },
      ]);
      setResult(response);
      setStages(response.stages);
      setDialogUsage(response.usage);
      setChats(await listChats());
      applyDetail(await getChat(selectedChatId));
      return response;
    } catch (requestError) {
      setMessages(current => current.slice(0, -1));
      if (requestError.status === 413) {
        setOverflow(requestError.message);
      } else {
        setError(requestError.message);
      }
      setStages(currentStages => currentStages.map(stage => ({
        ...stage,
        status: stage.name === 'DeepSeek API' ? 'error' : stage.status,
      })));
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmedMessage = message.trim();
    if (!trimmedMessage || !selectedChatId || loading || simulating || overflow) return;

    setMessage('');
    await sendToChat(trimmedMessage);
  }

  async function handleSimulate() {
    if (!selectedChatId || loading || simulating || overflow) return;

    setSimulating(true);
    try {
      for (let part = 1; part <= SIMULATION_PARTS; part += 1) {
        const response = await sendToChat(`Симуляция, часть ${part}. ${SIMULATION_FILLER.repeat(18)}`);
        if (!response) break;
      }
    } finally {
      setSimulating(false);
    }
  }

  async function handleCompare() {
    setComparing(true);
    setCompareError('');
    setCompareRows(null);
    try {
      const results = await runCompare();
      setCompareRows(results);
      setChats(await listChats());
    } catch (requestError) {
      setCompareError(requestError.message);
    } finally {
      setComparing(false);
    }
  }

  async function handleFork(messageIndex) {
    if (!selectedChatId) return;
    try {
      const detail = await createBranch(
        selectedChatId,
        messageIndex + 1,
        `ветка ${branches.length + 1}`
      );
      applyDetail(detail);
      setMessages(detail.messages);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleSwitchBranch(branchId) {
    if (!selectedChatId) return;
    try {
      const detail = await setActiveBranch(selectedChatId, branchId);
      applyDetail(detail);
      setMessages(detail.messages);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleDeleteBranch(branchId) {
    if (!selectedChatId || !window.confirm('Удалить эту ветку со всеми сообщениями?')) return;
    try {
      const detail = await deleteBranch(selectedChatId, branchId);
      applyDetail(detail);
      setMessages(detail.messages);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleFactsChange(nextFacts) {
    if (!selectedChatId) return;
    setFacts(nextFacts);
    try {
      applyDetail(await updateFacts(selectedChatId, nextFacts));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  return (
    <main className="page-shell">
      <header className="hero">
        <div className="eyebrow"><span className="pulse-dot" /> DAY 10 / CONTEXT STRATEGIES</div>
        <h1>Диалог, который<br /><em>не тонет в истории.</em></h1>
        <p className="hero-copy">
          Четыре стратегии памяти: полная история, скользящее окно,
          KV-facts и ветвление. Прогони один ТЗ-сценарий на всех —
          смотри, кто что теряет.
        </p>
      </header>

      <section className="workspace" aria-label="Token-aware agent workspace">
        <ChatSidebar
          chats={chats}
          disabled={loading || initializing || simulating}
          onCreate={handleCreateChat}
          onDelete={handleDeleteChat}
          onSelect={handleSelectChat}
          selectedChatId={selectedChatId}
        />
        <ChatPanel
          activeBranchId={activeBranchId}
          branches={branches}
          dialogUsage={dialogUsage}
          facts={facts}
          mode={mode}
          error={error}
          loading={loading || initializing}
          message={message}
          messages={messages}
          onChange={setMessage}
          onFactsChange={handleFactsChange}
          onFork={handleFork}
          onModeChange={handleModeChange}
          onDeleteBranch={handleDeleteBranch}
          onNewChat={handleCreateChat}
          onSimulate={handleSimulate}
          onSubmit={handleSubmit}
          onSwitchBranch={handleSwitchBranch}
          overflow={overflow}
          result={result}
          simulating={simulating}
        />
        <AgentFlow loading={loading} stages={stages} />
      </section>

      <ComparePanel
        comparing={comparing || loading}
        error={compareError}
        onOpenChat={handleSelectChat}
        onStart={handleCompare}
        rows={compareRows}
      />

      <footer className="page-footer">
        <span>FASTAPI + REACT</span>
        <span>TOKEN BUDGET</span>
      </footer>
    </main>
  );
}
