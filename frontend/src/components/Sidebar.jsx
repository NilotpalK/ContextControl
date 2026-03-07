import React, { useState } from 'react';
import { Network, Database, Search, MessageSquare, Plus, Trash2 } from 'lucide-react';
import '../index.css';

const TopicPill = ({ topic, onToggle }) => {
    const isHidden = topic.status === 'hidden';

    return (
        <div
            className={`topic-item ${isHidden ? 'hidden' : ''}`}
            onClick={() => onToggle(topic)}
            title={`Confidence: ${(topic.confidence || 1).toFixed(2)}\nReferences: ${topic.exchange_count}`}
        >
            <div className="topic-info" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Database size={14} color="var(--accent-color)" opacity={isHidden ? 0.4 : 1} />
                <span className="topic-name">{topic.name}</span>
            </div>
            <span className="topic-action" style={{ fontSize: '12px' }}>
                {isHidden ? 'Restore' : 'Block'}
            </span>
        </div>
    );
};

export default function Sidebar({ topics, onToggleTopic, sessionsList = [], currentSessionId, onSelectSession, onNewChat, onDeleteSession }) {
    const [searchQuery, setSearchQuery] = useState('');

    const filteredTopics = (topics || []).filter(t =>
        t.name.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="sidebar glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
            {/* Top Section: Chat History */}
            <div style={{ flex: '1 1 auto', overflowY: 'auto', marginBottom: '20px', paddingBottom: '20px', borderBottom: '1px solid var(--panel-border)' }}>
                <button
                    onClick={onNewChat}
                    className="glow-btn"
                    style={{ width: '100%', marginBottom: '20px' }}
                >
                    <Plus size={16} /> New Chat
                </button>

                <h3 style={{ fontSize: '13px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '12px', fontWeight: 600 }}>
                    Recent Chats
                </h3>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {sessionsList.map(session => (
                        <div
                            key={session.id}
                            onClick={() => onSelectSession(session.id)}
                            style={{
                                padding: '10px 12px',
                                borderRadius: '8px',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '10px',
                                background: currentSessionId === session.id ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                                border: '1px solid',
                                borderColor: currentSessionId === session.id ? 'var(--accent-color)' : 'transparent',
                                color: currentSessionId === session.id ? 'white' : 'var(--text-secondary)',
                                transition: 'all 0.2s',
                                fontSize: '14px'
                            }}
                            onMouseOver={e => {
                                if (currentSessionId !== session.id) {
                                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
                                    e.currentTarget.style.color = 'var(--text-primary)';
                                }
                            }}
                            onMouseOut={e => {
                                if (currentSessionId !== session.id) {
                                    e.currentTarget.style.background = 'transparent';
                                    e.currentTarget.style.color = 'var(--text-secondary)';
                                }
                            }}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', flex: 1, gap: '10px', overflow: 'hidden' }}>
                                <MessageSquare
                                    size={16}
                                    color={currentSessionId === session.id ? 'var(--accent-hover)' : 'var(--text-muted)'}
                                    style={{ minWidth: '16px' }}
                                />
                                <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                    {session.title || "New Conversation"}
                                </span>
                            </div>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    if (onDeleteSession) onDeleteSession(session.id);
                                }}
                                style={{
                                    background: 'transparent',
                                    border: 'none',
                                    padding: '4px',
                                    cursor: 'pointer',
                                    color: 'var(--text-muted)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    borderRadius: '4px',
                                    transition: 'color 0.2s',
                                }}
                                onMouseOver={e => { e.currentTarget.style.color = '#ef4444'; }}
                                onMouseOut={e => { e.currentTarget.style.color = 'var(--text-muted)'; }}
                                title="Delete Chat"
                            >
                                <Trash2 size={14} />
                            </button>
                        </div>
                    ))}
                    {sessionsList.length === 0 && (
                        <div style={{ color: 'var(--text-muted)', fontSize: '13px', padding: '10px' }}>
                            Loading history...
                        </div>
                    )}
                </div>
            </div>

            {/* Bottom Section: Active Context */}
            <div style={{ display: 'flex', flexDirection: 'column', height: '45%' }}>
                <div style={{ paddingBottom: '16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <Network size={20} color="var(--accent-hover)" />
                    <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Active Context</h2>
                </div>

                <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '20px', lineHeight: '1.5' }}>
                    The LLM pulls these topics from your memory graph. Click to block a topic from its context window.
                </p>

                <div style={{ position: 'relative', marginTop: '16px' }}>
                    <Search size={14} color="var(--text-muted)" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
                    <input
                        type="text"
                        placeholder="Search topics..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        style={{
                            width: '100%',
                            padding: '8px 12px 8px 30px',
                            background: 'rgba(0,0,0,0.2)',
                            border: '1px solid var(--panel-border)',
                            borderRadius: '6px',
                            color: 'white',
                            fontSize: '13px',
                            outline: 'none'
                        }}
                    />
                </div>

                <div className="topic-list">
                    {topics.length === 0 && (
                        <div style={{ color: 'var(--text-muted)', fontSize: '13px', textAlign: 'center', marginTop: '40px' }}>
                            No topics detected yet.
                        </div>
                    )}
                    {topics.length > 0 && filteredTopics.length === 0 && (
                        <div style={{ color: 'var(--text-muted)', fontSize: '13px', textAlign: 'center', marginTop: '40px' }}>
                            No matching topics found.
                        </div>
                    )}
                    {filteredTopics.map(t => (
                        <TopicPill key={t.name} topic={t} onToggle={onToggleTopic} />
                    ))}
                </div>
            </div>
        </div>
    );
}
