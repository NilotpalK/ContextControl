import React, { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import { getTopics, hideTopic, showTopic, streamChat, getSessionDetails, getAllSessions, api } from './api';

export default function App() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hello! I am connected to the ContextControl backend. How can I help you today?' }
  ]);
  const [topics, setTopics] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('context_session_id') || null);

  const fetchAllSessions = async () => {
    try {
      const data = await getAllSessions('user_1');
      if (data.sessions) setSessionsList(data.sessions);
    } catch (e) {
      console.error(e);
    }
  };

  const createNewSession = () => {
    api.post('/sessions', { user_id: 'user_1' })
      .then(res => {
        setSessionId(res.data.session_id);
        localStorage.setItem('context_session_id', res.data.session_id);
        setMessages([{ role: 'assistant', content: 'Hello! I am connected to the ContextControl backend. How can I help you today?' }]);
        setTopics([]); // Clear topics on new chat
        fetchAllSessions(); // Refresh list
      })
      .catch(err => console.error("Failed to create session:", err));
  };

  const loadSession = (id) => {
    setSessionId(id);
    localStorage.setItem('context_session_id', id);
    setTopics([]); // Clear while loading
    getSessionDetails(id).then(data => {
      if (data.exchanges && data.exchanges.length > 0) {
        const restoredMsgs = [{ role: 'assistant', content: 'Hello! I am connected to the ContextControl backend. How can I help you today?' }];
        data.exchanges.forEach(ex => {
          restoredMsgs.push({ role: 'user', content: ex.message });
          restoredMsgs.push({ role: 'assistant', content: ex.response });
        });
        setMessages(restoredMsgs);
      } else {
        setMessages([{ role: 'assistant', content: 'Hello! I am connected to the ContextControl backend. How can I help you today?' }]);
      }
    }).catch(err => {
      console.warn("Failed to load session details", err);
      createNewSession();
    });
  };

  // Create or Restore session on mount
  useEffect(() => {
    fetchAllSessions();
    if (sessionId) {
      loadSession(sessionId);
    } else {
      createNewSession();
    }
  }, []);

  // Poll topics every 3 seconds to get the background Kuzu graph updates
  useEffect(() => {
    if (!sessionId) return;
    const fetchTopics = async () => {
      try {
        const data = await getTopics(sessionId);
        if (data.topics) {
          setTopics(data.topics);
        }
      } catch (e) {
        // Ignore poll fails
      }
    };

    fetchTopics();
    const interval = setInterval(fetchTopics, 3000);
    return () => clearInterval(interval);
  }, [sessionId]);

  const handleToggleTopic = async (topic) => {
    const isHidden = topic.status === 'hidden';
    try {
      if (isHidden) {
        await showTopic(topic.name, sessionId);
      } else {
        await hideTopic(topic.name, sessionId);
      }
      // Instantly refresh topics
      const data = await getTopics(sessionId);
      if (data.topics) setTopics(data.topics);
    } catch (err) {
      console.error("Failed to toggle topic", err);
    }
  };

  const handleSendMessage = async (text) => {
    if (!sessionId) return;

    // Add user message
    const newMsgs = [...messages, { role: 'user', content: text }];
    setMessages(newMsgs);
    setIsStreaming(true);

    try {
      let assistantReply = "";

      await streamChat(text, sessionId, 'user_1', (chunk) => {
        assistantReply += chunk;
        setMessages([...newMsgs, { role: 'assistant', content: assistantReply }]);
      });

    } catch (e) {
      console.error(e);
      setMessages([...newMsgs, { role: 'assistant', content: '[Error connecting to backend]' }]);
    } finally {
      setIsStreaming(false);
      // Let the 3-second poller pick up new topics generated in the background
    }
  };

  return (
    <div className="app-container">
      <Sidebar
        topics={topics}
        onToggleTopic={handleToggleTopic}
        sessionsList={sessionsList}
        currentSessionId={sessionId}
        onSelectSession={loadSession}
        onNewChat={createNewSession}
      />
      <ChatWindow
        messages={messages}
        onSendMessage={handleSendMessage}
        isStreaming={isStreaming}
      />
    </div>
  );
}
