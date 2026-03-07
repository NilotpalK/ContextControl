import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL.replace(/\/$/, '') : 'http://localhost:10000';

export let GLOBAL_API_KEY = "";

export const api = axios.create({
    baseURL: API_BASE,
});

export const setGlobalApiKey = (key) => {
    GLOBAL_API_KEY = key;
    api.defaults.headers.common['Authorization'] = `Bearer ${key}`;
};

export const getTopics = async (sessionId) => {
    const res = await api.get(`/topics/${sessionId}`);
    return res.data;
};

export const hideTopic = async (topicName, sessionId) => {
    const res = await api.post('/topic/hide', {
        topic_name: topicName,
        session_id: sessionId
    });
    return res.data;
};

export const showTopic = async (topicName, sessionId) => {
    const res = await api.post('/topic/show', {
        topic_name: topicName,
        session_id: sessionId
    });
    return res.data;
};

export const getSessionDetails = async (sessionId) => {
    const res = await api.get(`/sessions/${sessionId}/detail`);
    return res.data;
};

export const getAllSessions = async (userId) => {
    const res = await api.get(`/sessions/${userId}`);
    return res.data;
};

export const deleteSession = async (sessionId) => {
    const res = await api.delete(`/sessions/${sessionId}`);
    return res.data;
};

export const streamChat = async (message, sessionId, userId, onChunk) => {
    const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${GLOBAL_API_KEY}`
        },
        body: JSON.stringify({
            session_id: sessionId,
            user_id: userId,
            message: message,
            system_prompt: "You are a helpful, concise AI assistant."
        })
    });

    if (!response.ok) {
        throw new Error('Network response was not ok');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        onChunk(chunk);
    }
};
