import React, { useState } from 'react';
import { Key } from 'lucide-react';
import '../index.css';

export default function LoginModal({ onKeySubmit }) {
    const [inputValue, setInputValue] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        if (inputValue.trim()) {
            onKeySubmit(inputValue.trim());
        }
    };

    return (
        <div style={{
            position: 'fixed',
            top: 0, left: 0, right: 0, bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999
        }}>
            <div className="glass-panel" style={{
                padding: '40px',
                borderRadius: '16px',
                width: '100%',
                maxWidth: '400px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '20px'
            }}>
                <div style={{
                    width: '48px', height: '48px',
                    borderRadius: '50%',
                    background: 'rgba(99, 102, 241, 0.15)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                    <Key size={24} color="var(--accent-hover)" />
                </div>
                <h2 style={{ fontSize: '24px', fontWeight: 600, textAlign: 'center' }}>Welcome Back</h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '14px', textAlign: 'center', lineHeight: 1.5 }}>
                    Please enter your OpenRouter API Key to continue. Your key is stored exclusively in your browser's volatile memory and is never saved to disk.
                </p>
                <form onSubmit={handleSubmit} style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <input
                        type="password"
                        placeholder="sk-or-v1-..."
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        autoFocus
                        style={{
                            width: '100%',
                            padding: '12px 16px',
                            background: 'rgba(0,0,0,0.3)',
                            border: '1px solid var(--panel-border)',
                            borderRadius: '8px',
                            color: 'white',
                            fontSize: '14px',
                            outline: 'none',
                        }}
                    />
                    <button type="submit" className="glow-btn" style={{ width: '100%', padding: '12px' }}>
                        Connect
                    </button>
                </form>
            </div>
        </div>
    );
}
