"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Terminal, Loader2, Bot } from "lucide-react";
import { interrogateAgent } from "@/lib/api";

type Message = {
  role: "system" | "human" | "agent";
  content: string;
};

export default function AgentChat() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "system", content: "Vyuha AI Terminal connected. Read-only access granted." }
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isTyping) return;

    const query = input.trim();
    setInput("");
    setMessages(prev => [...prev, { role: "human", content: query }]);
    setIsTyping(true);

    try {
      const reply = await interrogateAgent(query);
      setMessages(prev => [...prev, { role: "agent", content: reply }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: "system", content: "ERROR: Connection to Vyuha Orchestrator dropped." }]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="flex flex-col h-[500px] w-full bg-[#121214] border border-[#27272a] rounded-lg overflow-hidden shadow-2xl">
      <div className="bg-[#18181b] p-3 border-b border-[#27272a] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-vyuha-muted" />
          <h3 className="text-xs font-mono tracking-wider text-vyuha-muted">INTERROGATION CONSOLE</h3>
        </div>
        <div className="flex items-center gap-2">
           <div className="h-2 w-2 rounded-full bg-vyuha-success shadow-[0_0_8px_rgba(34,197,94,0.5)]"></div>
           <span className="text-[10px] uppercase font-bold text-vyuha-success">GLM-5.1 SECURE</span>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'human' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded p-3 text-sm ${
              msg.role === 'human' 
                ? 'bg-vyuha-primary/10 border border-vyuha-primary/30 text-white font-sans'
                : msg.role === 'system'
                ? 'bg-vyuha-warning/10 border border-vyuha-warning/30 text-vyuha-warning font-mono text-xs'
                : 'bg-[#18181b] border border-[#27272a] text-[#a1a1aa] font-mono leading-relaxed'
            }`}>
              {msg.role === 'agent' && <div className="flex items-center gap-2 mb-2 text-vyuha-primary"><Bot className="w-4 h-4" /> Vyuha AI</div>}
              {msg.content}
            </div>
          </div>
        ))}
        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-[#18181b] border border-[#27272a] rounded p-3 text-[#a1a1aa] font-mono">
              <Loader2 className="w-4 h-4 animate-spin" />
            </div>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="p-3 border-t border-[#27272a] bg-[#09090b]">
        <div className="relative flex items-center">
          <span className="absolute left-3 text-vyuha-primary font-mono">{">"}</span>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask why a node was disabled..."
            className="w-full bg-[#121214] border border-[#27272a] text-white text-sm rounded pl-8 pr-10 py-2.5 focus:outline-none focus:border-vyuha-primary/50 font-mono transition-colors"
            autoComplete="off"
            disabled={isTyping}
          />
          <button 
            type="submit" 
            disabled={!input.trim() || isTyping}
            className="absolute right-2 p-1.5 text-vyuha-primary hover:bg-vyuha-primary/10 rounded disabled:opacity-50 transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
