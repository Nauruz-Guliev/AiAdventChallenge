import { useEffect, useState } from 'react';
import {
  approveCandidate,
  clearHistory,
  completeWorkingMemory,
  createChat,
  deleteChat,
  deleteLongTermEntry,
  getChat,
  getLongTerm,
  listCandidates,
  listChats,
  rejectCandidate,
  replaceLongTerm,
  resetWorkingMemory,
  saveWorkingMemory,
  sendMessage,
} from './api.js';
import AgentFlow from './components/AgentFlow.jsx';
import CandidatesPanel from './components/CandidatesPanel.jsx';
import ChatPanel from './components/ChatPanel.jsx';
import ChatSidebar from './components/ChatSidebar.jsx';
import MemoryPanel from './components/MemoryPanel.jsx';

const initialStages = [
  { name: 'UI', status: 'completed' },
  { name: 'Agent', status: 'pending' },
  { name: 'DeepSeek API', status: 'pending' },
];

export default function App() {
  const [chats, setChats] = useState([]);
  const [selectedChatId, setSelectedChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [working, setWorking] = useState(null);
  const [longTerm, setLongTerm] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [message, setMessage] = useState('');
  const [result, setResult] = useState(null);
  const [stages, setStages] = useState(initialStages);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [dialogUsage, setDialogUsage] = useState(null);
  const [overflow, setOverflow] = useState('');

  function applyDetail(chat) {
    setMessages(chat.messages ?? []);
    setWorking(chat.working_memory ?? null);
    setDialogUsage(chat.dialog_usage ?? null);
  }

  async function refreshMemory() {
    setLongTerm(await getLongTerm());
    setCandidates(await listCandidates('pending'));
  }

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      try {
        let availableChats = await listChats();
        if (!availableChats.length) {
          availableChats = [await createChat()];
        }
        if (cancelled) return;
        setChats(availableChats);
        await loadChat(availableChats[0].id);
        await refreshMemory();
      } catch (requestError) {
        if (!cancelled) setError(requestError.message);
      } finally {
        if (!cancelled) setInitializing(false);
      }
    }

    boot();
    return () => {
      cancelled = true;
    };
  }, []);

  async function loadChat(chatId) {
    const chat = await getChat(chatId);
    setSelectedChatId(chat.id);
    setResult(null);
    setError('');
    setOverflow('');
    setStages(initialStages);
    applyDetail(chat);
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
    if (loading) return;
    try {
      const newChat = await createChat();
      setChats(current => [newChat, ...current]);
      setSelectedChatId(newChat.id);
      setMessages([]);
      setWorking(null);
      setResult(null);
      setDialogUsage(null);
      setOverflow('');
      setStages(initialStages);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleDeleteChat(chatId) {
    if (loading || !window.confirm('Удалить чат? Долговременная память сохранится.')) return;
    try {
      await deleteChat(chatId);
      const remaining = await listChats();
      if (remaining.length) {
        setChats(remaining);
        if (chatId === selectedChatId) await loadChat(remaining[0].id);
        return;
      }
      const newChat = await createChat();
      setChats([newChat]);
      await loadChat(newChat.id);
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
      const response = await sendMessage(selectedChatId, text);
      setMessages(current => [
        ...current,
        {
          role: 'assistant',
          content: response.answer,
          memory: response.usage?.memory ?? null,
        },
      ]);
      setResult(response);
      setStages(response.stages);
      setDialogUsage(response.usage);
      setChats(await listChats());
      applyDetail(await getChat(selectedChatId));
      await refreshMemory();
      return response;
    } catch (requestError) {
      setMessages(current => current.slice(0, -1));
      if (requestError.status === 413) {
        setOverflow(requestError.message);
      } else {
        setError(requestError.message);
      }
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || !selectedChatId || loading || overflow) return;
    setMessage('');
    await sendToChat(trimmed);
  }

  async function handleSaveWorking(nextWorking) {
    try {
      applyDetail(await saveWorkingMemory(selectedChatId, nextWorking));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleCompleteWorking() {
    try {
      applyDetail(await completeWorkingMemory(selectedChatId));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleResetWorking() {
    try {
      applyDetail(await resetWorkingMemory(selectedChatId));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleClearHistory() {
    if (!window.confirm('Очистить историю диалога? Рабочая и долговременная память останутся.')) return;
    try {
      applyDetail(await clearHistory(selectedChatId));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleAddEntry({ category, text }) {
    try {
      const next = {
        profile: longTerm?.profile ?? [],
        decisions: longTerm?.decisions ?? [],
        knowledge: longTerm?.knowledge ?? [],
      };
      next[category] = [
        ...next[category],
        { id: crypto.randomUUID(), text, source_chat_id: selectedChatId, created_at: new Date().toISOString() },
      ];
      setLongTerm(await replaceLongTerm(next));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleDeleteEntry(category, entryId) {
    try {
      await deleteLongTermEntry(category, entryId);
      await refreshMemory();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleApprove(candidateId) {
    try {
      await approveCandidate(candidateId);
      await refreshMemory();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleReject(candidateId) {
    try {
      await rejectCandidate(candidateId);
      await refreshMemory();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  const disabled = loading || initializing;

  return (
    <main className="page-shell">
      <header className="hero">
        <div className="eyebrow"><span className="pulse-dot" /> DAY 11 / ASSISTANT MEMORY</div>
        <h1>Три слоя памяти.<br /><em>Один ассистент.</em></h1>
        <p className="hero-copy">
          Краткосрочная — история диалога. Рабочая — карточка текущей задачи.
          Долговременная — профиль, решения, знания навсегда. Вы решаете,
          что и куда сохраняется.
        </p>
      </header>

      <section className="workspace">
        <ChatSidebar
          chats={chats}
          disabled={disabled}
          onCreate={handleCreateChat}
          onDelete={handleDeleteChat}
          onSelect={handleSelectChat}
          selectedChatId={selectedChatId}
        />
        <ChatPanel
          error={error}
          loading={disabled}
          message={message}
          messages={messages}
          onChange={setMessage}
          onNewChat={handleCreateChat}
          onSubmit={handleSubmit}
          overflow={overflow}
          result={result}
        />
        <MemoryPanel
          disabled={disabled}
          longTerm={longTerm}
          messageCount={messages.length}
          onAddEntry={handleAddEntry}
          onClearHistory={handleClearHistory}
          onCompleteWorking={handleCompleteWorking}
          onDeleteEntry={handleDeleteEntry}
          onResetWorking={handleResetWorking}
          onSaveWorking={handleSaveWorking}
          working={working}
        />
      </section>

      <CandidatesPanel
        candidates={candidates}
        disabled={disabled}
        onApprove={handleApprove}
        onReject={handleReject}
      />

      <section className="flow-row">
        <AgentFlow loading={disabled} stages={stages} />
      </section>

      <footer className="page-footer">
        <span>FASTAPI + REACT</span>
        <span>THREE-LAYER MEMORY</span>
      </footer>
    </main>
  );
}