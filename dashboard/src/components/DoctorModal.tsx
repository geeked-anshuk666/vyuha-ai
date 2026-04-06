"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  HeartPulse, Activity, Brain, Server, Shield, 
  X, CheckCircle2, AlertTriangle, Loader2 
} from "lucide-react";
import { checkLLMHealth, checkNodeHealthProxy, fetchStatus } from "@/lib/api";

interface DiagnosticResult {
  name: string;
  endpoint: string;
  status: "pending" | "healthy" | "unhealthy";
  latency?: number;
  error?: string;
  type: "orchestrator" | "proxy" | "node" | "llm";
}

export default function DoctorModal({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) {
  const [results, setResults] = useState<DiagnosticResult[]>([
    { name: "Orchestrator Core", endpoint: "/health", status: "pending", type: "orchestrator" },
    { name: "Dynamic Proxy", endpoint: "/health", status: "pending", type: "proxy" },
    { name: "Node-A (AWS Mock)", endpoint: "/chaos/node-a/health", status: "pending", type: "node" },
    { name: "Node-B (Azure Mock)", endpoint: "/chaos/node-b/health", status: "pending", type: "node" },
    { name: "Z.ai Cloud Handshake", endpoint: "/monitor/check-llm", status: "pending", type: "llm" },
  ]);

  const [isScanning, setIsScanning] = useState(false);

  const runDiagnostics = async () => {
    setIsScanning(true);
    // Reset statuses
    setResults(prev => prev.map(r => ({ ...r, status: "pending", error: undefined, latency: undefined })));

    const runCheck = async (index: number, fn: () => Promise<any>) => {
      const start = Date.now();
      try {
        const data = await fn();
        const latency = data.latency_ms || Date.now() - start;
        setResults(prev => {
          const next = [...prev];
          next[index] = { 
            ...next[index], 
            status: data.status === "unhealthy" ? "unhealthy" : "healthy", 
            latency,
            error: data.error
          };
          return next;
        });
      } catch (e) {
        setResults(prev => {
          const next = [...prev];
          next[index] = { ...next[index], status: "unhealthy", error: "Connection Refused" };
          return next;
        });
      }
    };

    // Run sequentially for better visual feedback
    await runCheck(0, fetchStatus); // Orchestrator
    await runCheck(1, () => fetch("/orchestrator-api/health").then(r => r.json())); // Proxy
    await runCheck(2, () => checkNodeHealthProxy("node-a"));
    await runCheck(3, () => checkNodeHealthProxy("node-b"));
    await runCheck(4, checkLLMHealth);

    setIsScanning(false);
  };

  useEffect(() => {
    if (isOpen) runDiagnostics();
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
        <motion.div 
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="w-full max-w-xl bg-vyuha-surface border border-vyuha-border rounded-2xl shadow-2xl overflow-hidden"
        >
          {/* Header */}
          <div className="px-6 py-4 bg-[#18181b] border-b border-vyuha-border flex items-center justify-between">
            <div className="flex items-center gap-3">
              <HeartPulse className="w-5 h-5 text-vyuha-primary animate-pulse" />
              <h2 className="text-lg font-bold text-white uppercase tracking-tight">System Global Pulse</h2>
            </div>
            <button onClick={onClose} className="p-1 hover:bg-white/10 rounded-full transition-colors">
              <X className="w-5 h-5 text-vyuha-muted" />
            </button>
          </div>

          {/* Body */}
          <div className="p-6 space-y-4">
            <div className="flex items-center justify-between text-xs font-mono text-vyuha-muted uppercase tracking-widest mb-2">
              <span>Endpoint Component</span>
              <span>Pulse Status</span>
            </div>

            <div className="space-y-3">
              {results.map((res) => (
                <div key={res.name} className="flex items-center justify-between p-4 bg-[#121214] border border-vyuha-border rounded-xl">
                  <div className="flex items-center gap-4">
                    <div className={`p-2 rounded-lg ${res.status === 'healthy' ? 'bg-vyuha-success/10 text-vyuha-success' : res.status === 'unhealthy' ? 'bg-vyuha-danger/10 text-vyuha-danger' : 'bg-white/5 text-vyuha-muted'}`}>
                      {res.type === 'orchestrator' && <Shield className="w-4 h-4" />}
                      {res.type === 'proxy' && <Activity className="w-4 h-4" />}
                      {res.type === 'node' && <Server className="w-4 h-4" />}
                      {res.type === 'llm' && <Brain className="w-4 h-4" />}
                    </div>
                    <div>
                      <div className="text-sm font-medium text-white">{res.name}</div>
                      <div className="text-xs font-mono text-vyuha-muted">{res.endpoint}</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    {res.latency && <span className="text-[10px] font-mono text-vyuha-muted">{res.latency}ms</span>}
                    {res.status === "pending" ? (
                      <Loader2 className="w-5 h-5 text-vyuha-primary animate-spin" />
                    ) : res.status === "healthy" ? (
                      <CheckCircle2 className="w-5 h-5 text-vyuha-success" />
                    ) : (
                      <div className="flex items-center gap-2 group relative">
                        <AlertTriangle className="w-5 h-5 text-vyuha-danger" />
                        {res.error && (
                          <div className="absolute right-full mr-2 px-2 py-1 bg-vyuha-danger text-[10px] text-white rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity">
                            {res.error}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Footer */}
          <div className="px-6 py-4 bg-[#09090b] border-t border-vyuha-border flex items-center justify-between">
            <div className="text-xs text-vyuha-muted">
              {isScanning ? "Scanning system pulse..." : "Diagnostics complete."}
            </div>
            <button 
              onClick={runDiagnostics}
              disabled={isScanning}
              className="flex items-center gap-2 px-4 py-2 bg-vyuha-primary hover:bg-vyuha-primary-hover text-white text-sm font-semibold rounded-lg transition-all disabled:opacity-50"
            >
              {isScanning ? <Loader2 className="w-4 h-4 animate-spin" /> : <HeartPulse className="w-4 h-4" />}
              {isScanning ? "RE-SCANNING..." : "RUN FULL DIAGNOSTICS"}
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
