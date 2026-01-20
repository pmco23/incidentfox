'use client';

import { useMemo, useState } from 'react';
import { RequireRole } from '@/components/RequireRole';
import { RequirePermission } from '@/components/RequirePermission';
import { apiFetch } from '@/lib/apiClient';
import { useIdentity } from '@/lib/useIdentity';
import { Bot, Play } from 'lucide-react';

export default function AdminAgentRunPage() {
  const { identity } = useIdentity();

  const [orgId, setOrgId] = useState(identity?.org_id || 'org1');
  const [teamNodeId, setTeamNodeId] = useState(identity?.team_node_id || 'teamA');
  const [agentName, setAgentName] = useState('triage');
  const [message, setMessage] = useState('hello');
  const [contextJson, setContextJson] = useState('{}');
  const [timeout, setTimeout] = useState<number | ''>('');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);

  const parsedContext = useMemo(() => {
    try {
      const v = JSON.parse(contextJson || '{}');
      if (typeof v === 'object' && v !== null) return v;
      return null;
    } catch {
      return null;
    }
  }, [contextJson]);

  const run = async () => {
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      if (!orgId.trim() || !teamNodeId.trim() || !agentName.trim() || !message.trim()) {
        throw new Error('org_id, team_node_id, agent_name, and message are required');
      }
      if (parsedContext === null) {
        throw new Error('context must be valid JSON object');
      }
      const payload: any = {
        org_id: orgId.trim(),
        team_node_id: teamNodeId.trim(),
        agent_name: agentName.trim(),
        message: message,
        context: parsedContext,
      };
      if (timeout !== '') payload.timeout = Number(timeout);

      const res = await apiFetch('/api/orchestrator/agents/run', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const text = await res.text();
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${text}`);
      setResult(text ? JSON.parse(text) : null);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <RequireRole role="admin" fallbackHref="/">
      <div className="p-8 max-w-4xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <Bot className="w-7 h-7 text-gray-500" />
          <div>
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Run Agent</h1>
            <p className="text-sm text-gray-500">Admin-only proxy run via orchestrator (no team tokens in the browser).</p>
          </div>
        </div>

        {error && (
          <div className="text-sm text-red-600 bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-900/40 rounded-lg p-3">
            {error}
          </div>
        )}

        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm space-y-4">
          <RequirePermission
            permission="admin:agent:run"
            fallback={
              <div className="text-sm text-gray-600 dark:text-gray-300">
                You don’t have permission to run agents (<span className="font-mono">admin:agent:run</span>).
              </div>
            }
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <div className="text-xs text-gray-500">org_id</div>
                <input
                  value={orgId}
                  onChange={(e) => setOrgId(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950"
                />
              </div>
              <div className="space-y-1">
                <div className="text-xs text-gray-500">team_node_id</div>
                <input
                  value={teamNodeId}
                  onChange={(e) => setTeamNodeId(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950"
                />
              </div>
              <div className="space-y-1">
                <div className="text-xs text-gray-500">agent_name</div>
                <input
                  value={agentName}
                  onChange={(e) => setAgentName(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 font-mono"
                />
              </div>
              <div className="space-y-1">
                <div className="text-xs text-gray-500">timeout (seconds, optional)</div>
                <input
                  value={timeout}
                  onChange={(e) => setTimeout(e.target.value ? Number(e.target.value) : '')}
                  type="number"
                  min={1}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950"
                />
              </div>
            </div>

            <div className="space-y-1">
              <div className="text-xs text-gray-500">message</div>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={4}
                className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950"
              />
            </div>

            <div className="space-y-1">
              <div className="text-xs text-gray-500">context (JSON object)</div>
              <textarea
                value={contextJson}
                onChange={(e) => setContextJson(e.target.value)}
                rows={6}
                className="w-full px-3 py-2 text-xs font-mono rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950"
              />
              {parsedContext === null ? (
                <div className="text-xs text-red-600">Invalid JSON.</div>
              ) : null}
            </div>

            <div className="flex items-center gap-2 pt-2">
              <button
                onClick={run}
                disabled={submitting}
                className="flex items-center gap-2 px-3 py-2 text-sm font-medium bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:opacity-60"
              >
                <Play className="w-4 h-4" />
                {submitting ? 'Running…' : 'Run agent'}
              </button>
            </div>
          </RequirePermission>
        </div>

        {result ? (
          <pre className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 shadow-sm overflow-auto text-xs font-mono text-gray-700 dark:text-gray-200 max-h-[70vh]">
            {JSON.stringify(result, null, 2)}
          </pre>
        ) : null}
      </div>
    </RequireRole>
  );
}


