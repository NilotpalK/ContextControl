import React, { useState } from 'react';
import { Network, Database, Search } from 'lucide-react';
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

export default function Sidebar({ topics, onToggleTopic }) {
    const [searchQuery, setSearchQuery] = useState('');

    const filteredTopics = topics.filter(t =>
        t.name.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="sidebar glass-panel">
            <div style={{ paddingBottom: '16px', borderBottom: '1px solid var(--panel-border)', display: 'flex', alignItems: 'center', gap: '10px' }}>
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
    );
}
