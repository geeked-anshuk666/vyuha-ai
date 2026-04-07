"use client";

import { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { Activity } from "lucide-react";
import { baseURL } from "@/lib/api";

export default function TrafficGraph() {
  const [data, setData] = useState<any[]>([]);
  const [totalRps, setTotalRps] = useState(0);
  const [failRate, setFailRate] = useState(0);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const res = await fetch(`${baseURL}/monitor/metrics`);
        const json = await res.json();
        if (json.history && json.history.length > 0) {
          setData(json.history);
          const latest = json.history[json.history.length - 1];
          setTotalRps((latest.success || 0) + (latest.fail || 0));
          const total = (latest.success || 0) + (latest.fail || 0);
          setFailRate(total > 0 ? Math.round(((latest.fail || 0) / total) * 100) : 0);
        }
      } catch (e) {
        // Silently fail if load tester is not running
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-6 bg-black/40 backdrop-blur-xl border border-white/5 rounded-2xl">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Activity className="w-5 h-5 text-vyuha-primary" />
          <h2 className="font-mono text-sm tracking-[0.2em] text-white/70 uppercase">Realtime Network Throughput</h2>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-xs font-mono bg-[#121214] px-3 py-1 rounded-full border border-[#27272a]">
            <span className="text-emerald-400">{totalRps} req/s</span>
          </div>
          {failRate > 0 && (
            <div className="text-xs font-mono bg-red-500/10 px-3 py-1 rounded-full border border-red-500/30 text-red-400 animate-pulse">
              ⚠ {failRate}% FAIL RATE
            </div>
          )}
        </div>
      </div>

      <div className="h-48 w-full">
        {data.length === 0 ? (
          <div className="h-full w-full flex flex-col items-center justify-center text-vyuha-muted text-sm italic border border-dashed border-vyuha-border rounded-lg gap-3">
            <Activity className="w-5 h-5 animate-pulse text-vyuha-primary" />
            Connecting to Z.ai Gen-Engine Pulse...
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorSuccess" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22C55E" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#22C55E" stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="colorFail" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#EF4444" stopOpacity={0.4}/>
                  <stop offset="95%" stopColor="#EF4444" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <XAxis dataKey="time" stroke="#52525B" fontSize={10} tickMargin={8} minTickGap={30} />
              <YAxis stroke="#52525B" fontSize={10} />
              <Tooltip
                contentStyle={{ backgroundColor: '#121214', border: '1px solid #27272a', borderRadius: '8px' }}
                itemStyle={{ fontSize: '12px', fontFamily: 'monospace' }}
              />
              <Legend wrapperStyle={{ fontSize: '10px', fontFamily: 'monospace' }} />
              <Area type="monotone" dataKey="success" stroke="#22C55E" strokeWidth={2} fillOpacity={1} fill="url(#colorSuccess)" name="OK (200)" />
              <Area type="monotone" dataKey="fail" stroke="#EF4444" strokeWidth={2} fillOpacity={1} fill="url(#colorFail)" name="FAILED / KILLED" />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

