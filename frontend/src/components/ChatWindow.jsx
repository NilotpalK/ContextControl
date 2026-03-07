import React, { useRef, useEffect, useState } from 'react';
import { Send, Cpu } from 'lucide-react';

const Loader = () => (
    <div className="loader">
        <div className="loader-dot"></div>
        <div className="loader-dot"></div>
        <div className="loader-dot"></div>
    </div>
);

export default function ChatWindow({ messages, onSendMessage, isStreaming }) {
    const [input, setInput] = useState('');
    const bottomRef = useRef(null);

    // Auto-scroll to bottom of chat
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isStreaming]);

    const handleSubmit = (e) => {
        e.preventDefault();
        if (!input.trim() || isStreaming) return;
        onSendMessage(input);
        setInput('');
    };

    return (
        <div className="main-chat">
            <div className="chat-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ width: 36, height: 36, borderRadius: 18, background: 'var(--accent-glow)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Cpu size={20} color="var(--accent-color)" />
                    </div>
                    <div>
                        <h1 style={{ fontSize: '16px', fontWeight: 600 }}>Tagger Assistant</h1>
                        <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Graph RAG Enabled</p>
                    </div>
                </div>
            </div>

            <div className="chat-messages">
                {messages.map((m, i) => (
                    <div key={i} className={`message ${m.role === 'user' ? 'user' : 'assistant'}`}>
                        <div className="message-bubble">
                            {m.content}
                        </div>
                    </div>
                ))}
                {isStreaming && (
                    <div className="message assistant">
                        <div className="message-bubble">
                            <Loader />
                        </div>
                    </div>
                )}
                <div ref={bottomRef} />
            </div>

            <div className="chat-input-container">
                <form className="chat-form glass-panel" onSubmit={handleSubmit}>
                    <input
                        type="text"
                        className="chat-input"
                        placeholder="Ask about your databases or code..."
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        disabled={isStreaming}
                        autoFocus
                    />
                    <button type="submit" className="chat-submit-btn" disabled={!input.trim() || isStreaming}>
                        <Send size={18} />
                    </button>
                </form>
            </div>
        </div>
    );
}
