import React, { useState, useEffect, useRef } from 'react';

export default function AIChatPanel({ contextMode, onAction }) {
    // contextMode: 'cleaning' | 'design' | 'results'
    const [messages, setMessages] = useState([
        { role: 'assistant', content: 'Привет! Я изучил загруженные данные. В таблице есть несколько проблем с названиями колонок. Хотите, я их исправлю?' }
    ]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const bottomRef = useRef(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim()) return;
        const userMsg = { role: 'user', content: input };
        setMessages(prev => [...prev, userMsg]);
        setInput("");
        setLoading(true);

        try {
            // TODO: Connect to backend endpoint /api/v2/ai_system/chat
            // For now, mock response
            setTimeout(() => {
                setMessages(prev => [...prev, {
                    role: 'assistant',
                    content: 'Понял. Я могу удалить строки с пустыми значениями в колонке "Возраст". Выполнить это действие?',
                    actions: [
                        { label: "Удалить пустые", code: "DROP_NA_AGE" }
                    ]
                }]);
                setLoading(false);
            }, 1000);
        } catch {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-white border-l shadow-xl w-[400px]">
            {/* Header */}
            <div className="p-4 border-b bg-indigo-600 text-white flex justify-between items-center">
                <h3 className="font-bold">AI Ассистент</h3>
                <span className="text-xs bg-indigo-500 px-2 py-1 rounded capitalize">{contextMode} Mode</span>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
                {messages.map((m, idx) => (
                    <div key={idx} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[85%] p-3 rounded-lg text-sm ${m.role === 'user'
                                ? 'bg-indigo-600 text-white rounded-br-none'
                                : 'bg-white border text-gray-800 rounded-bl-none shadow-sm'
                            }`}>
                            <p>{m.content}</p>
                            {m.actions && (
                                <div className="mt-3 flex flex-col gap-2">
                                    {m.actions.map((act, i) => (
                                        <button
                                            key={i}
                                            onClick={() => onAction(act.code)}
                                            className="text-xs bg-indigo-50 text-indigo-700 px-3 py-2 rounded border border-indigo-200 hover:bg-indigo-100 text-left flex items-center gap-2"
                                        >
                                            <span>⚡️</span> {act.label}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                ))}
                {loading && (
                    <div className="flex justify-start">
                        <div className="bg-white border p-3 rounded-lg rounded-bl-none shadow-sm text-gray-400 text-xs italic">
                            Печатает...
                        </div>
                    </div>
                )}
                <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t bg-white">
                <div className="flex gap-2">
                    <input
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                        className="flex-1 border p-2 rounded focus:ring-2 focus:ring-indigo-500 outline-none text-sm"
                        placeholder="Напишите сообщение..."
                    />
                    <button
                        onClick={handleSend}
                        disabled={loading}
                        className="bg-indigo-600 text-white p-2 rounded hover:bg-indigo-700 transition"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
                    </button>
                </div>
            </div>
        </div>
    );
}
