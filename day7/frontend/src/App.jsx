import { useEffect, useState } from 'react';
import { createChat, getChat, listChats, sendMessage } from './api.js';
import AgentFlow from './components/AgentFlow.jsx';
import ChatPanel from './components/ChatPanel.jsx';
import ChatSidebar from './components/ChatSidebar.jsx';

const initialStages = [
  { name: 'UI', status: 'completed' },
  { name: 'Agent', status: 'pending' },
  { name: 'DeepSeek API', status: 'pending' },
];

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
    setError('');
    try {
      const newChat = await createChat();
      setChats(current => [newChat, ...current]);
      setSelectedChatId(newChat.id);
      setMessages([]);
      setResult(null);
      setStages(initialStages);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmedMessage = message.trim();
    if (!trimmedMessage || !selectedChatId || loading) return;

    const previousMessages = messages;
    setLoading(true);
    setMessage('');
    setError('');
    setResult(null);
    setStages([
      { name: 'UI', status: 'completed' },
      { name: 'Agent', status: 'active' },
      { name: 'DeepSeek API', status: 'pending' },
    ]);

    try {
      const response = await sendMessage(selectedChatId, trimmedMessage);
      setMessages(current => [
        ...current,
        { role: 'user', content: trimmedMessage },
        { role: 'assistant', content: response.answer },
      ]);
      setResult(response);
      setStages(response.stages);
      setChats(await listChats());
    } catch (requestError) {
      setMessages(previousMessages);
      setError(requestError.message);
      setStages(currentStages => currentStages.map(stage => ({
        ...stage,
        status: stage.name === 'DeepSeek API' ? 'error' : stage.status,
      })));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-shell">
      <header className="hero">
        <div className="eyebrow"><span className="pulse-dot" /> DAY 07 / CONTEXT PERSISTENCE</div>
        <h1>Разговор, который<br /><em>не исчезает.</em></h1>
        <p className="hero-copy">
          История живёт в JSON, поэтому агент помнит контекст даже после перезапуска приложения.
        </p>
      </header>

      <section className="workspace" aria-label="Persistent agent workspace">
        <ChatSidebar
          chats={chats}
          disabled={loading || initializing}
          onCreate={handleCreateChat}
          onSelect={handleSelectChat}
          selectedChatId={selectedChatId}
        />
        <ChatPanel
          error={error}
          loading={loading || initializing}
          message={message}
          messages={messages}
          onChange={setMessage}
          onSubmit={handleSubmit}
          result={result}
        />
        <AgentFlow loading={loading} stages={stages} />
      </section>

      <footer className="page-footer">
        <span>FASTAPI + REACT</span>
        <span>PERSISTENT JSON CONTEXT</span>
      </footer>
    </main>
  );
}
