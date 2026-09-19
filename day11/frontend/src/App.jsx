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
import ChatPanel from './components/ChatPanel.jsx';
import MemoryMap from './components/MemoryMap.jsx';
import SessionStrip from './components/SessionStrip.jsx';

export default function App() {
  const [chats, setChats] = useState([]);
  const [selectedChatId, setSelectedChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [working, setWorking] = useState(null);
  const [longTerm, setLongTerm] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [message, setMessage] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [overflow, setOverflow] = useState('');

  function applyDetail(chat) {
    setMessages(chat.messages ?? []);
    setWorking(chat.working_memory ?? null);
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
      setOverflow('');
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
    const used = {
      historyCount: messages.length,
      working: working
        ? {
            goal: working.goal,
            constraints: [...working.constraints],
            decisions: [...working.decisions],
          }
        : null,
      longTerm: longTerm
        ? {
            profile: longTerm.profile.map(entry => entry.text),
            decisions: longTerm.decisions.map(entry => entry.text),
            knowledge: longTerm.knowledge.map(entry => entry.text),
          }
        : null,
    };
    setLoading(true);
    setError('');
    setResult(null);
    setMessages(current => [...current, { role: 'user', content: text }]);

    try {
      const response = await sendMessage(selectedChatId, text);
      setMessages(current => [
        ...current,
        { role: 'assistant', content: response.answer, used },
      ]);
      setResult(response);
      setChats(await listChats());
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

  async function handleApprove(candidateId, payload) {
    try {
      await approveCandidate(candidateId, payload);
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
  const recent = messages.slice(-4);

  return (
    <main className="app">
      <header className="masthead">
        <div>
          <h1>Память ассистента</h1>
          <p>
            Три раздельных слоя: диалог, карточка текущей задачи и то, что вы
            решили помнить всегда.
          </p>
        </div>
        <ul className="legend">
          <li><span className="swatch mist" /> Краткосрочная</li>
          <li><span className="swatch amber" /> Рабочая</li>
          <li><span className="swatch deep" /> Долговременная</li>
        </ul>
      </header>

      <section className="split">
        <MemoryMap
          candidates={candidates}
          chats={chats}
          disabled={disabled}
          longTerm={longTerm}
          messageCount={messages.length}
          onAddEntry={handleAddEntry}
          onApprove={handleApprove}
          onClearHistory={handleClearHistory}
          onCompleteWorking={handleCompleteWorking}
          onDeleteEntry={handleDeleteEntry}
          onReject={handleReject}
          onResetWorking={handleResetWorking}
          onSaveWorking={handleSaveWorking}
          recent={recent}
          working={working}
        />
        <div className="col-dialog">
          <SessionStrip
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
        </div>
      </section>
    </main>
  );
}
