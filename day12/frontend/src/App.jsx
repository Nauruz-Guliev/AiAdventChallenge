import { useEffect, useState } from 'react';
import {
  activateProfile,
  approveCandidate,
  clearHistory,
  completeWorkingMemory,
  createChat,
  createProfile,
  createProfileFromPreset,
  deleteChat,
  deleteLongTermEntry,
  deleteProfile,
  getChat,
  getLongTerm,
  getProfilePresets,
  getProfiles,
  listCandidates,
  listChats,
  rejectCandidate,
  replaceLongTerm,
  resetWorkingMemory,
  saveWorkingMemory,
  sendMessage,
  updateProfile,
} from './api.js';
import ChatPanel from './components/ChatPanel.jsx';
import ConfirmDialog from './components/ConfirmDialog.jsx';
import MemoryMap from './components/MemoryMap.jsx';
import SessionStrip from './components/SessionStrip.jsx';

const TONE_LABELS = { formal: 'деловой тон', friendly: 'дружелюбный тон', neutral: 'нейтральный тон' };
const LENGTH_LABELS = { short: 'коротко', medium: 'средне', detailed: 'подробно' };
const STRUCTURE_LABELS = { prose: 'текст', bullets: 'списки', markdown: 'markdown' };

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
  const [confirmState, setConfirmState] = useState(null);
  const [profileStore, setProfileStore] = useState({ active_id: '', profiles: [] });
  const [presets, setPresets] = useState([]);

  function applyDetail(chat) {
    setMessages(chat.messages ?? []);
    setWorking(chat.working_memory ?? null);
  }

  async function refreshMemory() {
    setLongTerm(await getLongTerm());
    setCandidates(await listCandidates('pending'));
  }

  async function refreshProfiles() {
    const [store, presetList] = await Promise.all([
      getProfiles(),
      getProfilePresets(),
    ]);
    setProfileStore(store);
    setPresets(presetList);
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
        await refreshProfiles();
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

  function requestDeleteChat(chatId) {
    if (loading) return;
    setConfirmState({
      title: 'Удалить чат?',
      body: 'Сообщения этого чата исчезнут. Долговременная память сохранится.',
      confirmLabel: 'Удалить',
      onConfirm: () => {
        setConfirmState(null);
        performDeleteChat(chatId);
      },
    });
  }

  async function performDeleteChat(chatId) {
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
    setMessages(current => [...current, { role: 'user', content: text }]);

    try {
      const response = await sendMessage(selectedChatId, text);
      setMessages(current => [
        ...current,
        { role: 'assistant', content: response.answer, used: response.used ?? null },
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
      return true;
    } catch (requestError) {
      setError(requestError.message);
      return false;
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

  function requestClearHistory() {
    if (loading) return;
    setConfirmState({
      title: 'Очистить историю диалога?',
      body: 'Сообщения этого чата будут удалены. Рабочая и долговременная память останутся.',
      confirmLabel: 'Очистить',
      onConfirm: () => {
        setConfirmState(null);
        performClearHistory();
      },
    });
  }

  async function performClearHistory() {
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
      return true;
    } catch (requestError) {
      setError(requestError.message);
      return false;
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

  async function handleActivateProfile(profileId) {
    try {
      await activateProfile(profileId);
      await refreshProfiles();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleCreateProfileFromPreset(key) {
    try {
      await createProfileFromPreset(key);
      await refreshProfiles();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleDuplicateProfile(profile) {
    if (!profile) return;
    const base = (profile.title || 'Профиль').slice(0, 52);
    try {
      await createProfile({
        title: `${base} (копия)`,
        name: profile.name,
        role: profile.role,
        language: profile.language,
        tone: profile.tone,
        length: profile.length,
        structure: profile.structure,
        constraints: profile.constraints,
      });
      await refreshProfiles();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleUpdateProfile(profileId, fields) {
    try {
      await updateProfile(profileId, fields);
      await refreshProfiles();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  function requestDeleteProfile(profileId) {
    setConfirmState({
      title: 'Удалить профиль?',
      body: 'Профиль исчезнет из переключателя. Чаты и память останутся.',
      confirmLabel: 'Удалить',
      onConfirm: () => {
        setConfirmState(null);
        performDeleteProfile(profileId);
      },
    });
  }

  async function performDeleteProfile(profileId) {
    try {
      await deleteProfile(profileId);
      await refreshProfiles();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  const activeProfile =
    profileStore.profiles.find(item => item.id === profileStore.active_id) ?? null;
  const profileOff = Boolean(
    activeProfile &&
      activeProfile.tone === 'neutral' &&
      activeProfile.length === 'medium' &&
      activeProfile.structure === 'prose' &&
      !(activeProfile.constraints ?? []).length &&
      !activeProfile.name &&
      !activeProfile.role,
  );
  const profileSignature = activeProfile
    ? [
        TONE_LABELS[activeProfile.tone],
        LENGTH_LABELS[activeProfile.length],
        STRUCTURE_LABELS[activeProfile.structure],
        ...(activeProfile.constraints ?? []),
      ]
        .filter(Boolean)
        .join(' · ')
    : '';
  const disabled = loading || initializing;
  const recent = messages.slice(-4);

  return (
    <main className="app">
      <header className="masthead">
        <div>
          <h1>Персонализация ассистента</h1>
          <p>
            Профиль задаёт стиль, объём, формат и ограничения и подключается к
            каждому запросу. Память дня 11 живёт отдельно и свёрнута ниже.
          </p>
        </div>
        {activeProfile && (
          <div className="signature" aria-label="Активный профиль">
            <span className="signature-label mono">профиль</span>
            <span className="signature-title">
              {activeProfile.title || 'Без названия'}
            </span>
            <span className="signature-meta mono">
              {profileOff ? 'персонализация выключена' : profileSignature}
            </span>
          </div>
        )}
      </header>

      <div className="spine" aria-hidden="true" />

      <section className="split">
        <MemoryMap
          activeProfile={activeProfile}
          candidates={candidates}
          chats={chats}
          disabled={disabled}
          longTerm={longTerm}
          messageCount={messages.length}
          onActivateProfile={handleActivateProfile}
          onAddEntry={handleAddEntry}
          onApprove={handleApprove}
          onClearHistory={requestClearHistory}
          onCompleteWorking={handleCompleteWorking}
          onCreateFromPreset={handleCreateProfileFromPreset}
          onDeleteEntry={handleDeleteEntry}
          onDuplicateProfile={handleDuplicateProfile}
          onReject={handleReject}
          onRequestDeleteProfile={requestDeleteProfile}
          onResetWorking={handleResetWorking}
          onSaveWorking={handleSaveWorking}
          onUpdateProfile={handleUpdateProfile}
          presets={presets}
          profiles={profileStore.profiles}
          recent={recent}
          working={working}
        />
        <div className="col-dialog">
          <SessionStrip
            chats={chats}
            disabled={disabled}
            onCreate={handleCreateChat}
            onDelete={requestDeleteChat}
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

      {confirmState && (
        <ConfirmDialog
          body={confirmState.body}
          confirmLabel={confirmState.confirmLabel}
          onCancel={() => setConfirmState(null)}
          onConfirm={confirmState.onConfirm}
          open
          title={confirmState.title}
        />
      )}
    </main>
  );
}
