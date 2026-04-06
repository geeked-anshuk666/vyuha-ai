"use client";

import { useState, useLayoutEffect, useRef } from "react";
import { Info, HelpCircle, X, ArrowRight, ArrowLeft } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const TOUR_STEPS = [
  {
    title: "1. The Live Traffic Graph",
    target: "#traffic-graph-container",
    desc: "Observe the active background python script hitting the proxy 50 times per second. Green represents 200 HTTP successes. Red tracks dropped requests. When chaos is injected, watch this plummet and heal.",
  },
  {
    title: "2. The Network Topology",
    target: "#topology-container",
    desc: "These are the target cloud VMs (Node-A running an AWS mock, Node-B running Azure). Vyuha AI pings these every 5 seconds to generate health snapshots.",
  },
  {
    title: "3. Chaos Engineering Controls",
    target: "#chaos-controls-container",
    desc: "Click '1.5s LATENCY' or 'DEAD' to physically damage the downstream nodes. This forces Vyuha AI to detect the anomaly and perform triage.",
  },
  {
    title: "4. The Agent Companion",
    target: "#proposals-container",
    desc: "When a node fails, GLM-5.1 kicks in. It analyzes the incident, calculates a config proxy swap, checks its memory, and asks you for approval to execute.",
  },
  {
    title: "5. Autonomous SRE",
    target: "#proposals-container",
    desc: "Notice when the Agent proposes to reroute, it ALSO proposes a 'restart_node' SRE action. Upon your approval, the LLM physically executes the restart CLI against the broken node.",
  },
  {
    title: "6. Agent Interrogation",
    target: "#chat-container",
    desc: "Use the terminal below to ask GLM-5.1 questions about why it made a specific decision. It has contextual read-only access to the entire Incident Log.",
  },
  {
    title: "7. Evolutionary Memory",
    target: "#memory-container",
    desc: "Every time you 'Reject' an agent's proposal, it reflects on your feedback and stores a permanent Rule in its JSON Database. It uses this rule forever.",
  }
];

export default function WalkthroughOverlay() {
  const [isOpen, setIsOpen] = useState(true);
  const [currentStep, setCurrentStep] = useState(0);
  const [coords, setCoords] = useState({ top: 0, left: 0, width: 0, height: 0, ready: false });
  const overlayRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!isOpen) return;

    const updatePosition = () => {
      const step = TOUR_STEPS[currentStep];
      const element = document.querySelector(step.target);
      
      if (element) {
        const rect = element.getBoundingClientRect();
        // Position tooltip to the right or bottom of the element
        // For our grid, we'll try to center it or place it logically
        const isLeftColumn = step.target.includes('topology') || step.target.includes('chaos');
        const isTop = step.target.includes('traffic');
        
        let targetTop = rect.top + window.scrollY;
        let targetLeft = rect.left + window.scrollX;

        if (isTop) {
          // Below the graph
          targetTop = rect.bottom + 20;
          targetLeft = rect.left + (rect.width / 2) - 160;
        } else if (isLeftColumn) {
          // To the right of the column
          targetTop = rect.top;
          targetLeft = rect.right + 20;
        } else {
          // To the left of the right column components
          targetTop = rect.top;
          targetLeft = rect.left - 340;
        }

        // Clamp to screen
        targetLeft = Math.max(20, Math.min(targetLeft, window.innerWidth - 340));
        targetTop = Math.max(20, Math.min(targetTop, window.innerHeight - 250));

        setCoords({ top: targetTop, left: targetLeft, width: rect.width, height: rect.height, ready: true });
      } else {
        // Fallback to bottom right if target not found
        setCoords({ 
          top: window.innerHeight - 300, 
          left: window.innerWidth - 340, 
          width: 0, 
          height: 0, 
          ready: true 
        });
      }
    };

    updatePosition();
    window.addEventListener("resize", updatePosition);
    return () => window.removeEventListener("resize", updatePosition);
  }, [currentStep, isOpen]);

  if (!isOpen) {
    return (
      <button 
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 bg-vyuha-primary text-white p-3 rounded-full shadow-lg hover:bg-vyuha-primary-hover transition-colors z-[100] flex items-center gap-2"
      >
        <HelpCircle className="w-5 h-5" />
        <span className="text-sm font-semibold pr-2">Launch Tour</span>
      </button>
    );
  }

  const step = TOUR_STEPS[currentStep];

  return (
    <AnimatePresence>
      <motion.div 
        ref={overlayRef}
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ 
          opacity: coords.ready ? 1 : 0, 
          scale: 1, 
          top: coords.top, 
          left: coords.left 
        }}
        exit={{ opacity: 0, scale: 0.9 }}
        transition={{ type: "spring", damping: 25, stiffness: 200 }}
        className="fixed w-80 bg-[#121214] border border-vyuha-primary/40 rounded-xl shadow-[0_20px_50px_rgba(0,0,0,0.9)] z-[100] overflow-hidden"
      >
        {/* Pointer Arrow */}
        <div className="absolute -left-2 top-10 w-4 h-4 bg-[#121214] border-l border-t border-vyuha-primary/40 rotate-[-45deg] hidden lg:block" />

        {/* Header */}
        <div className="bg-[#18181b] px-4 py-3 border-b border-[#27272a] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-vyuha-primary" />
            <h3 className="text-xs font-mono tracking-wider text-vyuha-muted uppercase">Interactive Tour</h3>
          </div>
          <button onClick={() => setIsOpen(false)} className="text-vyuha-muted hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5">
          <div className="text-xs text-vyuha-primary font-mono mb-2">STEP {currentStep + 1} OF {TOUR_STEPS.length}</div>
          <h2 className="text-base font-bold text-white mb-3 leading-tight">{step.title}</h2>
          <p className="text-sm text-[#a1a1aa] leading-relaxed">{step.desc}</p>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 bg-[#09090b] border-t border-[#27272a] flex items-center justify-between">
          <button 
             onClick={() => setCurrentStep(prev => Math.max(0, prev - 1))}
             disabled={currentStep === 0}
             className="p-1.5 text-vyuha-muted hover:text-white disabled:opacity-20 transition-colors"
          >
             <ArrowLeft className="w-4 h-4" />
          </button>
          
          <div className="flex gap-1.5">
            {TOUR_STEPS.map((_, i) => (
              <div key={i} className={`h-1.5 w-1.5 rounded-full ${i === currentStep ? 'bg-vyuha-primary' : 'bg-[#27272a]'}`} />
            ))}
          </div>

          <button 
             onClick={() => {
               if (currentStep === TOUR_STEPS.length - 1) setIsOpen(false);
               else setCurrentStep(prev => Math.min(TOUR_STEPS.length - 1, prev + 1));
             }}
             className="px-3 py-1.5 bg-vyuha-primary text-white text-xs font-semibold rounded hover:bg-vyuha-primary-hover flex items-center gap-1 transition-colors"
          >
             {currentStep === TOUR_STEPS.length - 1 ? 'Finish' : <><span className="sr-only">Next</span><ArrowRight className="w-4 h-4"/></>}
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

