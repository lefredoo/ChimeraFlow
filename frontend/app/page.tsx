"use client";

import { useEffect, useState } from "react";

export default function Home() {
  const [apiStatus, setApiStatus] = useState<string>("checking...");
  const [apiVersion, setApiVersion] = useState<string>("");

  useEffect(() => {
    const checkAPI = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const response = await fetch(`${apiUrl}/health`);
        const data = await response.json();
        
        if (data.status === "ok") {
          setApiStatus("✓ Connected");
          setApiVersion(data.version || "0.1.0");
        } else {
          setApiStatus("✗ Error");
        }
      } catch (error) {
        setApiStatus("✗ Unreachable");
        console.error("API connection failed:", error);
      }
    };

    checkAPI();
  }, []);

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 dark:from-slate-900 dark:to-slate-800 p-8">
      <div className="max-w-4xl mx-auto">
        {/* Hero Section */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold bg-gradient-to-r from-blue-600 to-sky-500 bg-clip-text text-transparent mb-4 font-display">
            ChimeraFlow
          </h1>
          <p className="text-lg text-slate-600 dark:text-slate-300">
            Stitching Excel, Access, and WhatsApp into one correlated view
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
            Kiroween 2026 | Category: Frankenstein
          </p>
        </div>

        {/* Glass Card - API Status */}
        <div className="glass-panel rounded-2xl p-8 mb-8">
          <h2 className="text-2xl font-semibold mb-4 text-slate-800 dark:text-slate-100">
            API Status
          </h2>
          
          <div className="space-y-3">
            <div className="flex items-center justify-between py-3 px-4 bg-white/50 dark:bg-slate-800/50 rounded-lg">
              <span className="text-slate-600 dark:text-slate-300 font-mono text-sm">
                Backend API
              </span>
              <span className={`font-medium ${
                apiStatus.includes("✓") 
                  ? "text-emerald-600 dark:text-emerald-400" 
                  : "text-red-600 dark:text-red-400"
              }`}>
                {apiStatus}
              </span>
            </div>
            
            {apiVersion && (
              <div className="flex items-center justify-between py-3 px-4 bg-white/50 dark:bg-slate-800/50 rounded-lg">
                <span className="text-slate-600 dark:text-slate-300 font-mono text-sm">
                  Version
                </span>
                <span className="text-slate-800 dark:text-slate-100 font-medium font-mono">
                  {apiVersion}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Feature Cards */}
        <div className="grid md:grid-cols-3 gap-6 mb-8">
          <FeatureCard
            title="Excel"
            description="Supplier price lists with imperfect formatting"
            icon="📊"
          />
          <FeatureCard
            title="Access"
            description="Legacy stock databases (.mdb)"
            icon="🗄️"
          />
          <FeatureCard
            title="WhatsApp"
            description="Customer orders and messages"
            icon="💬"
          />
        </div>

        {/* P0 Status */}
        <div className="glass-panel rounded-2xl p-6">
          <h3 className="text-lg font-semibold mb-3 text-slate-800 dark:text-slate-100">
            Phase P0 - Foundations
          </h3>
          <p className="text-sm text-slate-600 dark:text-slate-300 mb-4">
            Hello-world bout en bout | Spike Access | 3 Specs
          </p>
          <div className="flex gap-2">
            <span className="px-3 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full text-xs font-medium">
              In Progress
            </span>
          </div>
        </div>
      </div>

      <style jsx global>{`
        .glass-panel {
          background: rgba(255, 255, 255, 0.7);
          backdrop-filter: blur(12px);
          border: 1px solid rgba(255, 255, 255, 0.18);
          box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
        }
        
        @media (prefers-color-scheme: dark) {
          .glass-panel {
            background: rgba(17, 24, 39, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.1);
          }
        }
      `}</style>
    </main>
  );
}

function FeatureCard({ title, description, icon }: { title: string; description: string; icon: string }) {
  return (
    <div className="glass-panel rounded-xl p-6 hover:scale-105 transition-transform duration-200">
      <div className="text-4xl mb-3">{icon}</div>
      <h3 className="text-lg font-semibold mb-2 text-slate-800 dark:text-slate-100">
        {title}
      </h3>
      <p className="text-sm text-slate-600 dark:text-slate-300">
        {description}
      </p>
    </div>
  );
}
