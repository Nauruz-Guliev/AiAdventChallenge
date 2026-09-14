import { useEffect, useState } from 'react';
import { createChat, deleteChat, getChat, listChats, sendMessage } from './api.js';
import AgentFlow from './components/AgentFlow.jsx';
import ChatPanel from './components/ChatPanel.jsx';
import ChatSidebar from './components/ChatSidebar.jsx';

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
  const [compress, setCompress] = useState(
    () => localStorage.getItem('day9-compress') !== 'false'
  );

  function handleToggleCompress() {
    setCompress(current => {
      localStorage.setItem('day9-compress', String(!current));
      return !current;
    });
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
      const response = await sendMessage(selectedChatId, text, compress);
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
          compression: response.usage?.compression ?? null,
        },
      ]);
      setResult(response);
      setStages(response.stages);
      setDialogUsage(response.usage);
      setChats(await listChats());
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

  return (
    <main className="page-shell">
      <header className="hero">
        <div className="eyebrow"><span className="pulse-dot" /> DAY 09 / CONTEXT COMPRESSION</div>
        <h1>Диалог, который<br /><em>не тонет в истории.</em></h1>
        <p className="hero-copy">
          Старые сообщения сворачиваются в summary, хвост остаётся как есть.
          Сравнивай качество и расход токенов с тумблером сжатия.
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
          compress={compress}
          dialogUsage={dialogUsage}
          error={error}
          loading={loading || initializing}
          message={message}
          messages={messages}
          onToggleCompress={handleToggleCompress}
          onChange={setMessage}
          onNewChat={handleCreateChat}
          onSimulate={handleSimulate}
          onSubmit={handleSubmit}
          overflow={overflow}
          result={result}
          simulating={simulating}
        />
        <AgentFlow loading={loading} stages={stages} />
      </section>

      <footer className="page-footer">
        <span>FASTAPI + REACT</span>
        <span>TOKEN BUDGET</span>
      </footer>
    </main>
  );
}
