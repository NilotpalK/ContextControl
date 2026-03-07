import React from 'react';
import { AlertTriangle, X } from 'lucide-react';
import '../index.css';

export default function ConfirmModal({ onConfirm, onCancel, title, message }) {
    return (
        <div style={{
            position: 'fixed',
            top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0,0,0,0.6)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999
        }}>
            <div className="glass-panel" style={{
                width: '400px',
                padding: '24px',
                borderRadius: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '16px',
                position: 'relative',
                animation: 'slideIn 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
            }}>
                <button
                    onClick={onCancel}
                    style={{
                        position: 'absolute',
                        top: '16px',
                        right: '16px',
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--text-muted)',
                        cursor: 'pointer',
                        display: 'flex',
                    }}
                >
                    <X size={18} />
                </button>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--text-primary)' }}>
                    <div style={{
                        background: 'rgba(239, 68, 68, 0.15)',
                        padding: '8px',
                        borderRadius: '8px',
                        display: 'flex'
                    }}>
                        <AlertTriangle size={20} color="#ef4444" />
                    </div>
                    <h3 style={{ fontSize: '18px', fontWeight: 600 }}>{title || 'Confirm Action'}</h3>
                </div>

                <p style={{ color: 'var(--text-secondary)', fontSize: '14px', lineHeight: '1.5' }}>
                    {message || 'Are you sure you want to proceed? This action cannot be undone.'}
                </p>

                <div style={{ display: 'flex', gap: '12px', marginTop: '8px', justifyContent: 'flex-end' }}>
                    <button
                        onClick={onCancel}
                        style={{
                            padding: '10px 16px',
                            background: 'rgba(255, 255, 255, 0.05)',
                            border: '1px solid var(--panel-border)',
                            color: 'var(--text-primary)',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            fontSize: '14px',
                            fontWeight: 500,
                            transition: 'background 0.2s'
                        }}
                        onMouseOver={e => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)'}
                        onMouseOut={e => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={onConfirm}
                        style={{
                            padding: '10px 16px',
                            background: '#ef4444',
                            border: 'none',
                            color: 'white',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            fontSize: '14px',
                            fontWeight: 500,
                            boxShadow: '0 0 12px rgba(239, 68, 68, 0.3)',
                            transition: 'all 0.2s'
                        }}
                        onMouseOver={e => {
                            e.currentTarget.style.background = '#dc2626';
                            e.currentTarget.style.boxShadow = '0 0 20px rgba(239, 68, 68, 0.5)';
                            e.currentTarget.style.transform = 'translateY(-1px)';
                        }}
                        onMouseOut={e => {
                            e.currentTarget.style.background = '#ef4444';
                            e.currentTarget.style.boxShadow = '0 0 12px rgba(239, 68, 68, 0.3)';
                            e.currentTarget.style.transform = 'none';
                        }}
                    >
                        Delete Chat
                    </button>
                </div>
            </div>
        </div>
    );
}
