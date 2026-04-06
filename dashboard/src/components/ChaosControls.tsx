"use client";

import { useState } from "react";

export default function ChaosControls() {
  const [loading, setLoading] = useState<string | null>(null);

  const injectChaos = async (nodeName: string, state: string, reason: string) => {
    setLoading(`${nodeName}-${state}`);
    try {
      // Because we mapped /api/node-a/ to docker node-a:8000
      await fetch(`/api/${nodeName}/fail`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state, reason }),
      });
    } catch (e) {
      console.error("Chaos injection failed", e);
    } finally {
      setLoading(null);
    }
  };

  const recoverNode = async (nodeName: string) => {
    setLoading(`${nodeName}-recover`);
    try {
      await fetch(`/api/${nodeName}/recover`, { method: "POST" });
    } catch (e) {
      console.error("Recovery failed", e);
    } finally {
      setLoading(null);
    }
  };

  const NodeControls = ({ nodeName }: { nodeName: string }) => (
    <div className="flex flex-col gap-2 p-4 bg-white/5 border border-white/10 rounded-xl">
      <div className="flex items-center justify-between">
        <h3 className="font-mono text-sm tracking-widest text-[#FFB073]">{nodeName.toUpperCase()}</h3>
        <button
          onClick={() => recoverNode(nodeName)}
          disabled={!!loading}
          className="px-3 py-1 text-xs font-mono bg-green-500/20 text-green-400 border border-green-500/30 rounded shadow-[0_0_10px_rgba(34,197,94,0.1)] hover:bg-green-500/30 transition-colors"
        >
          {loading === `${nodeName}-recover` ? "RECOVERING..." : "HEAL (RECOVER)"}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-2 mt-2">
        <button
          onClick={() => injectChaos(nodeName, "high_latency", "Fiber cut induced severe latency")}
          disabled={!!loading}
          className="px-2 py-2 text-xs font-mono bg-yellow-500/20 text-yellow-500 hover:bg-yellow-500/30 border border-yellow-500/30 rounded flex flex-col items-center gap-1 transition-colors disabled:opacity-50"
        >
          <span>1.5s LATENCY</span>
        </button>

        <button
          onClick={() => injectChaos(nodeName, "flaky", "Network switch intermittently dropping packets")}
          disabled={!!loading}
          className="px-2 py-2 text-xs font-mono bg-orange-500/20 text-orange-500 hover:bg-orange-500/30 border border-orange-500/30 rounded flex flex-col items-center gap-1 transition-colors disabled:opacity-50"
        >
          <span>FLAKY (25% FAIL)</span>
        </button>

        <button
          onClick={() => injectChaos(nodeName, "dead", "Complete datacenter power failure")}
          disabled={!!loading}
          className="px-2 py-2 text-xs font-mono bg-red-500/20 text-red-500 hover:bg-red-500/30 border border-red-500/30 rounded flex flex-col items-center gap-1 transition-colors disabled:opacity-50"
        >
          <span>HARD KILL (DEAD)</span>
        </button>
      </div>
    </div>
  );

  return (
    <div className="p-6 bg-black/40 backdrop-blur-xl border border-white/5 rounded-2xl">
      <div className="flex items-center gap-3 mb-6">
        <div className="h-2 w-2 rounded-full bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.8)] animate-pulse" />
        <h2 className="font-mono text-sm tracking-[0.2em] text-white/70">CHAOS EXPERIMENTS</h2>
      </div>

      <div className="space-y-4">
        <NodeControls nodeName="node-a" />
        <NodeControls nodeName="node-b" />
      </div>
    </div>
  );
}
