"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Server, Activity, ShieldAlert, Cpu, Terminal, 
  ChevronRight, CheckCircle2, XCircle, RefreshCw, AlertTriangle
} from "lucide-react";
import { 
  fetchStatus, fetchProposals, fetchLearnings, 
  triggerTriage, approveProposal, rejectProposal, 
  MonitorStatus, NodeState 
} from "@/lib/api";
import ChaosControls from "@/components/ChaosControls";
import TrafficGraph from "@/components/TrafficGraph";
import AgentChat from "@/components/AgentChat";
import WalkthroughOverlay from "@/components/WalkthroughOverlay";

interface Proposal {
  id: number;
  agent_reasoning: string;
  formation_change: {
    action: string;
    target_node: string;
    remediation_action?: string;
    proposed_config: Record<string, unknown>;
    confidence: number;
  };
}

interface Learning {
  id: number;
  incident_id: number;
  lesson_learned: string;
  agent_reflection: string;
  human_feedback?: string;
  was_approved: boolean;
  created_at: string;
}

export default function MissionControl() {
  const [status, setStatus] = useState<MonitorStatus | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [learnings, setLearnings] = useState<Learning[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  const [feedback, setFeedback] = useState("");
  const [processingId, setProcessingId] = useState<number | null>(null);

  const loadData = async () => {
    setIsRefreshing(true);
    try {
      const [statusData, proposalsData, learningsData] = await Promise.all([
        fetchStatus(),
        fetchProposals(),
        fetchLearnings()
      ]);
      setStatus(statusData);
      setProposals(proposalsData);
      setLearnings(learningsData);
    } catch (error) {
      console.error("Dashboard failed to fetch data:", error);
    }
    setIsRefreshing(false);
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleTriage = async () => {
    await triggerTriage();
    loadData();
  };

  const handleAction = async (proposalId: number, type: "approve" | "reject") => {
    console.log(`[DASHBOARD] Triggering ${type} for proposal ${proposalId}`);
    setProcessingId(proposalId);
    try {
      if (type === "approve") {
        await approveProposal(proposalId, feedback || "Approved via Dashboard");
      } else {
        await rejectProposal(proposalId, feedback || "Rejected via Dashboard");
      }
      setFeedback("");
      console.log(`[DASHBOARD] Successfully ${type}d proposal ${proposalId}`);
    } catch (e: unknown) {
      const error = e as Error;
      console.error(`[DASHBOARD] Action ${type} failed:`, error);
      alert(`Critical Error: Could not ${type} proposal. Check console for details.`);
    }
    setProcessingId(null);
    loadData();
  };

  if (!status) {
    return <div className="flex h-screen items-center justify-center bg-vyuha-bg text-vyuha-muted"><RefreshCw className="animate-spin w-8 h-8" /></div>;
  }

  return (
    <div className="min-h-screen p-8 max-w-7xl mx-auto space-y-8 pb-20">
      
      {/* Header */}
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
            <Cpu className="text-vyuha-primary" />
            Vyuha AI: Mission Control
          </h1>
          <p className="text-vyuha-muted mt-1">Autonomous Multi-Cloud Recovery Orchestrator</p>
        </div>
        <div className="flex gap-4 items-center">
          <div className="text-sm px-3 py-1 rounded-full bg-vyuha-surface border border-vyuha-border text-vyuha-muted">
            Uptime: {status.orchestrator_uptime}s
          </div>
          <button 
            onClick={loadData}
            className="p-2 rounded-full hover:bg-vyuha-surface transition-colors text-vyuha-muted border border-vyuha-border"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? "animate-spin" : ""}`} />
          </button>
        </div>
      </header>
      
      {/* Circuit Breaker Warning */}
      {status.circuit_breaker_active && (
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="bg-vyuha-danger-bg border border-vyuha-danger text-vyuha-danger p-4 rounded-lg flex items-start gap-4">
          <AlertTriangle className="shrink-0 mt-0.5" />
          <div>
            <h3 className="font-bold">CIRCUIT BREAKER ACTIVE</h3>
            <p className="text-sm">Agent autonomy disabled due to repeated failures. Manual override required.</p>
          </div>
        </motion.div>
      )}

      {/* Traffic Graph Insert */}
      <div id="traffic-graph-container" className="mb-8">
        <TrafficGraph />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column: Network Topology */}
        <div className="lg:col-span-1 space-y-8">
          <section id="topology-container" className="glass-panel p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                <Activity className="w-5 h-5" /> Network Topology
              </h2>
              <button onClick={handleTriage} className="text-xs bg-vyuha-primary hover:bg-vyuha-primary-hover text-white px-3 py-1.5 rounded transition">
                Force Triage
              </button>
            </div>
            
            <div className="space-y-4">
              {status.node_states.map((node: NodeState) => (
                <div key={node.node_name} className="flex items-center justify-between p-4 rounded-lg bg-[#121214] border border-[#27272a]">
                  <div className="flex items-center gap-3">
                    <Server className={node.state === "HEALTHY" ? "text-vyuha-success" : "text-vyuha-danger"} />
                    <div>
                      <div className="font-medium text-white">{node.node_name.toUpperCase()}</div>
                      <div className="text-xs text-vyuha-muted">Seen: {new Date(node.checked_at).toLocaleTimeString()}</div>
                    </div>
                  </div>
                  <div className={`px-2 py-1 text-xs font-bold rounded ${node.state === "HEALTHY" ? "bg-vyuha-success-bg text-vyuha-success" : "bg-vyuha-danger-bg text-vyuha-danger"}`}>
                    {node.state}
                  </div>
                </div>
              ))}
            </div>

            <div id="chaos-controls-container" className="mt-8">
              <ChaosControls />
            </div>
            
            <div className="mt-6 pt-6 border-t border-vyuha-border">
               <h3 className="text-sm font-medium text-vyuha-muted mb-4 uppercase tracking-wider">Active Incidents</h3>
               {status.active_incidents.length === 0 ? (
                 <p className="text-sm text-vyuha-muted italic">All systems nominal.</p>
               ) : (
                 <div className="space-y-2">
                   {status.active_incidents.map((inc: any) => (
                     <div key={inc.id} className="text-sm p-3 bg-vyuha-warning-bg border border-vyuha-warning text-vyuha-warning rounded">
                       <span className="font-bold">#{inc.id}</span> • {inc.description}
                     </div>
                   ))}
                 </div>
               )}
            </div>
          </section>
        </div>

        {/* Right Column: AI Insights & Human Loop */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* Glass Break: Pending Proposals */}
          <section id="proposals-container" className="glass-panel p-6 shadow-[0_0_30px_rgba(59,130,246,0.1)]">
            <h2 className="text-xl font-semibold text-white flex items-center gap-2 mb-6">
              <ShieldAlert className="w-5 h-5 text-vyuha-primary" /> 
              Companion Insight
            </h2>
            
            <AnimatePresence>
              {proposals.length === 0 ? (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-10 border border-dashed border-vyuha-border rounded-lg">
                  <p className="text-vyuha-muted">No pending agent proposals.</p>
                </motion.div>
              ) : (
                <div className="space-y-6">
                  {proposals.map(prop => (
                    <motion.div 
                      key={prop.id}
                      initial={{ opacity: 0, scale: 0.98 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, height: 0 }}
                      className="bg-[#121214] border border-vyuha-primary/30 rounded-lg overflow-hidden"
                    >
                      <div className="p-5 border-b border-vyuha-border">
                        <div className="flex justify-between items-start mb-3">
                          <div>
                            <span className="text-xs font-mono text-vyuha-primary bg-vyuha-primary/10 px-2 py-1 rounded">
                              PROPOSAL #{prop.id}
                            </span>
                            <h3 className="text-lg font-medium text-white mt-2">
                              {prop.formation_change.action.toUpperCase()} target: {prop.formation_change.target_node}
                            </h3>
                            {prop.formation_change.remediation_action && prop.formation_change.remediation_action !== "none" && (
                               <div className="inline-block mt-2 px-2 py-1 bg-vyuha-warning/20 border border-vyuha-warning/40 text-vyuha-warning text-xs font-mono rounded">
                                 + SRE ACTION: {prop.formation_change.remediation_action}
                               </div>
                            )}
                          </div>
                          <div className="text-right">
                            <div className="text-2xl font-bold text-white">{(prop.formation_change.confidence * 100).toFixed(0)}%</div>
                            <div className="text-xs text-vyuha-muted uppercase">Confidence</div>
                          </div>
                        </div>
                        <p className="text-sm font-serif text-vyuha-muted mb-4 border-l-2 border-vyuha-primary/50 pl-3">
                          &quot;{prop.agent_reasoning}&quot;
                        </p>
                        
                        <div className="bg-[#09090b] p-3 rounded font-mono text-xs text-vyuha-muted overflow-x-auto">
                          {JSON.stringify(prop.formation_change.proposed_config, null, 2)}
                        </div>
                      </div>
                      
                      <div className="p-4 bg-vyuha-surface flex flex-col sm:flex-row gap-4 items-center">
                        <input 
                          type="text" 
                          placeholder="Add human feedback (optional)..."
                          className="flex-1 bg-vyuha-bg border border-vyuha-border rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-vyuha-primary"
                          value={feedback}
                          onChange={(e) => setFeedback(e.target.value)}
                          disabled={processingId === prop.id}
                        />
                        <div className="flex gap-2 w-full sm:w-auto">
                          <button 
                            disabled={processingId === prop.id}
                            onClick={() => handleAction(prop.id, "reject")}
                            className="flex-1 sm:flex-none px-4 py-2 border border-vyuha-border hover:bg-vyuha-danger/20 hover:text-vyuha-danger hover:border-vyuha-danger text-white text-sm font-medium rounded transition flex items-center justify-center gap-2"
                          >
                            <XCircle className="w-4 h-4" /> Reject
                          </button>
                          <button 
                            disabled={processingId === prop.id}
                            onClick={() => handleAction(prop.id, "approve")}
                            className="flex-1 sm:flex-none px-4 py-2 bg-vyuha-primary hover:bg-vyuha-primary-hover text-white text-sm font-medium rounded transition flex items-center justify-center gap-2"
                          >
                            <CheckCircle2 className="w-4 h-4" /> {processingId === prop.id ? "Validating..." : "Approve"}
                          </button>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </AnimatePresence>
          </section>

          {/* Agent Interrogation Chat */}
          <section id="chat-container" className="glass-panel p-6">
            <h2 className="text-xl font-semibold text-white flex items-center gap-2 mb-6">
              <Terminal className="w-5 h-5 text-vyuha-primary" /> 
              Agent Interrogation
            </h2>
            <AgentChat />
          </section>

          {/* Evolutionary Memory Feed */}
          <section id="memory-container" className="glass-panel p-6">
             <h2 className="text-xl font-semibold text-white flex items-center gap-2 mb-6">
              <ChevronRight className="w-5 h-5 text-vyuha-muted" /> 
              Evolutionary Memory Log
            </h2>
            
            <div className="space-y-4">
              {learnings.length === 0 ? (
                <p className="text-sm text-vyuha-muted italic">No learnings recorded yet.</p>
              ) : (
                [...learnings].reverse().map(l => (
                  <div key={l.id} className="flex gap-4 relative pb-4">
                    <div className="absolute top-8 left-[11px] bottom-0 w-px border-l-2 border-dashed border-vyuha-border"></div>
                    <div className={`mt-1 z-10 w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${l.was_approved ? 'bg-vyuha-success/20 text-vyuha-success' : 'bg-vyuha-danger/20 text-vyuha-danger'}`}>
                      {l.was_approved ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                    </div>
                    <div className="flex-1 bg-[#121214] border border-[#27272a] rounded-lg p-4">
                      <div className="flex justify-between items-start mb-2">
                        <span className="text-xs font-mono text-vyuha-muted">INCIDENT #{l.incident_id}</span>
                        <span className="text-xs bg-vyuha-surface px-2 py-0.5 rounded text-vyuha-muted border border-vyuha-border">
                          {new Date(l.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <p className="text-sm text-white font-medium mb-3">{l.lesson_learned}</p>
                      
                      <div className="text-xs text-vyuha-muted bg-[#09090b] p-3 rounded border-l-2 border-[#27272a]">
                        <div className="mb-1"><span className="uppercase font-bold tracking-wider opacity-70">Agent Reflection:</span> {l.agent_reflection}</div>
                        {l.human_feedback && <div className="mt-2 text-white"><span className="uppercase font-bold tracking-wider opacity-70 text-vyuha-primary">Human Feedback:</span> &quot;{l.human_feedback}&quot;</div>}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>

        </div>
      </div>

      {/* Guide Overlay */}
      <WalkthroughOverlay />
    </div>
  );
}
