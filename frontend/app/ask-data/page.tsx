'use client';

import { DashboardLayout } from '@/components/dashboard-layout';
import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '@/lib/api';
import { Send, User, Bot, Sparkles } from 'lucide-react';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

const suggestionQueries = [
  'What is our highest pain point by segment?',
  'Show me the top feature requests this month',
  'Which competitor is taking the most deals?',
  'What is the trend in NPS scores?',
];

export default function AskYourDataPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Welcome to Ask Your Data! I can help you explore customer feedback insights, sentiment analysis, and VOC metrics. Try asking me questions like **"What is our highest pain point?"** or **"Show feature requests by category"**.',
      timestamp: new Date(),
    },
  ]);

  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading]);

  const handleSendMessage = async (queryText?: string) => {
    const textToSend = queryText || input.trim();
    if (!textToSend) return;

    const userMessage: ChatMessage = {
      id: String(Date.now()),
      role: 'user',
      content: textToSend,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await api.post('/dashboard/chat', { question: textToSend });
      const data = response.data;
      
      const assistantMessage: ChatMessage = {
        id: String(Date.now() + 1),
        role: 'assistant',
        content: data.answer || "I'm sorry, I couldn't generate an answer.",
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Chat error:", error);
      const errorMessage: ChatMessage = {
        id: String(Date.now() + 1),
        role: 'assistant',
        content: 'There was an error communicating with the AI. Please try again later.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="flex flex-col h-[calc(100vh-8rem)] w-full">
        {/* Chat Area */}
        <div className="flex-1 min-h-0 bg-card border border-border rounded-xl shadow-sm flex flex-col overflow-hidden">
          {/* Messages Container */}
          <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex gap-4 ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
              >
                {/* Avatar */}
                <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${
                  message.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-secondary border border-border text-foreground'
                }`}>
                  {message.role === 'user' ? <User size={20} /> : <Bot size={20} />}
                </div>

                {/* Message Bubble */}
                <div
                  className={`max-w-[80%] rounded-2xl px-6 py-4 ${
                    message.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary/40 text-foreground border border-border'
                  }`}
                >
                  <div className={`prose prose-sm max-w-none ${message.role === 'user' ? 'prose-invert' : 'dark:prose-invert'}
                                   prose-p:leading-relaxed prose-pre:bg-secondary prose-pre:border prose-pre:border-border`}
                  >
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {message.content}
                    </ReactMarkdown>
                  </div>
                  <span className={`text-[10px] block mt-2 opacity-60 ${message.role === 'user' ? 'text-right' : 'text-left'}`}>
                    {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            ))}
            
            {/* Loading Indicator */}
            {isLoading && (
              <div className="flex gap-4 flex-row">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-secondary border border-border text-foreground flex items-center justify-center">
                  <Bot size={20} />
                </div>
                <div className="bg-secondary/40 text-foreground border border-border rounded-2xl px-6 py-4 flex items-center space-x-2">
                  <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area (Sticky at bottom inside the card) */}
          <div className="p-4 bg-card border-t border-border">
            {messages.length === 1 && (
              <div className="mb-4">
                <p className="text-xs uppercase tracking-widest font-semibold text-muted-foreground mb-3 px-1">Try asking:</p>
                <div className="flex flex-wrap gap-2">
                  {suggestionQueries.map((query, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSendMessage(query)}
                      className="px-4 py-2 bg-secondary/50 hover:bg-secondary border border-border rounded-full transition-colors text-xs text-foreground font-medium"
                    >
                      {query}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center gap-3 relative">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                placeholder="Ask your data anything..."
                disabled={isLoading}
                className="flex-1 bg-input/50 border border-border rounded-full pl-6 pr-14 py-4 text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:bg-input transition-all duration-200"
              />
              <button
                onClick={() => handleSendMessage()}
                disabled={isLoading || !input.trim()}
                className="absolute right-2 top-1/2 -translate-y-1/2 bg-primary hover:bg-primary/90 disabled:opacity-40 disabled:hover:bg-primary text-primary-foreground p-2 rounded-full transition-all duration-200"
                aria-label="Send message"
              >
                <Send size={18} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
