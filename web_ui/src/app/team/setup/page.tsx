'use client';

import { useState, useEffect, useCallback } from 'react';
import { useIdentity } from '@/lib/useIdentity';
import { CheckCircle, AlertCircle, ArrowRight, ExternalLink } from 'lucide-react';

interface RequiredField {
  path: string;
  display_name: string;
  description: string;
  field_type: string;
}

interface IntegrationSchema {
  id: string;
  name: string;
  description: string;
  level: string;
  team_fields: {
    name: string;
    type: string;
    required: boolean;
    display_name: string;
    description: string;
    placeholder?: string;
    default?: unknown;
  }[];
}

const COMMON_INTEGRATIONS: IntegrationSchema[] = [
  {
    id: 'grafana',
    name: 'Grafana',
    description: 'Connect your Grafana instance for metrics and dashboards',
    level: 'team',
    team_fields: [
      {
        name: 'base_url',
        type: 'string',
        required: true,
        display_name: 'Grafana URL',
        description: 'Your Grafana instance URL',
        placeholder: 'https://grafana.example.com',
      },
      {
        name: 'api_key',
        type: 'secret',
        required: true,
        display_name: 'API Key',
        description: 'Service account token or API key',
      },
    ],
  },
  {
    id: 'kubernetes',
    name: 'Kubernetes',
    description: 'Configure your default namespace',
    level: 'team',
    team_fields: [
      {
        name: 'default_namespace',
        type: 'string',
        required: false,
        display_name: 'Default Namespace',
        description: 'Your team\'s primary namespace',
        default: 'default',
      },
      {
        name: 'allowed_namespaces',
        type: 'string',
        required: false,
        display_name: 'Allowed Namespaces',
        description: 'Comma-separated list of namespaces your team can access',
      },
    ],
  },
  {
    id: 'slack',
    name: 'Slack',
    description: 'Configure Slack notifications',
    level: 'team',
    team_fields: [
      {
        name: 'default_channel',
        type: 'string',
        required: false,
        display_name: 'Default Channel',
        description: 'Channel for incident notifications',
        placeholder: '#team-incidents',
      },
      {
        name: 'mention_oncall',
        type: 'boolean',
        required: false,
        display_name: 'Mention On-Call',
        description: 'Whether to mention on-call in notifications',
        default: true,
      },
    ],
  },
];

export default function TeamSetupPage() {
  const { identity, loading: identityLoading } = useIdentity();
  const [step, setStep] = useState(0);
  const [requiredFields, setRequiredFields] = useState<RequiredField[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [configValues, setConfigValues] = useState<Record<string, Record<string, string>>>({});
  const [error, setError] = useState<string | null>(null);
  const [isComplete, setIsComplete] = useState(false);

  const loadRequiredFields = useCallback(async () => {
    if (!identity?.org_id || !identity?.team_node_id) return;
    setLoading(true);
    
    try {
      const res = await fetch('/api/team/config/required-fields');
      if (res.ok) {
        const data = await res.json();
        setRequiredFields(data.missing || []);
        setIsComplete(data.missing?.length === 0);
      }
    } catch (e) {
      console.error('Failed to load required fields', e);
    } finally {
      setLoading(false);
    }
  }, [identity?.org_id, identity?.team_node_id]);

  useEffect(() => {
    loadRequiredFields();
  }, [loadRequiredFields]);

  const saveIntegrationConfig = async (integrationId: string) => {
    if (!identity?.org_id || !identity?.team_node_id) return;
    setSaving(true);
    setError(null);
    
    const values = configValues[integrationId] || {};
    
    try {
      const res = await fetch('/api/team/config', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          config: {
            integrations: {
              [integrationId]: {
                team_config: values,
              },
            },
          },
        }),
      });
      
      if (res.ok) {
        // Move to next step
        if (step < COMMON_INTEGRATIONS.length - 1) {
          setStep(step + 1);
        } else {
          // Check if complete
          await loadRequiredFields();
        }
      } else {
        const data = await res.json();
        setError(data.detail || 'Failed to save configuration');
      }
    } catch (e) {
      setError('Failed to save configuration');
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const updateFieldValue = (integrationId: string, fieldName: string, value: string) => {
    setConfigValues((prev) => ({
      ...prev,
      [integrationId]: {
        ...prev[integrationId],
        [fieldName]: value,
      },
    }));
  };

  if (identityLoading || loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
        <div className="animate-pulse">Loading setup wizard...</div>
      </div>
    );
  }

  if (isComplete) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
        <div className="max-w-md text-center">
          <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-6" />
          <h1 className="text-2xl font-bold text-white mb-4">Setup Complete!</h1>
          <p className="text-slate-400 mb-8">
            Your team is configured and ready to use IncidentFox.
          </p>
          <a
            href="/team/agent-runs"
            className="inline-flex items-center gap-2 px-6 py-3 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors"
          >
            Go to Dashboard
            <ArrowRight className="w-4 h-4" />
          </a>
        </div>
      </div>
    );
  }

  const currentIntegration = COMMON_INTEGRATIONS[step];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Progress */}
      <div className="border-b border-slate-800 bg-slate-900/50 px-8 py-6">
        <div className="max-w-2xl mx-auto">
          <h1 className="text-2xl font-bold text-white mb-2">Team Setup</h1>
          <p className="text-slate-400">Configure your team's integrations</p>
          
          {/* Progress Steps */}
          <div className="flex gap-2 mt-6">
            {COMMON_INTEGRATIONS.map((int, idx) => (
              <div
                key={int.id}
                className={`flex-1 h-2 rounded-full ${
                  idx < step
                    ? 'bg-green-500'
                    : idx === step
                      ? 'bg-cyan-500'
                      : 'bg-slate-700'
                }`}
              />
            ))}
          </div>
          <div className="flex justify-between mt-2 text-sm text-slate-500">
            {COMMON_INTEGRATIONS.map((int) => (
              <span key={int.id}>{int.name}</span>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-2xl mx-auto p-8">
        {error && (
          <div className="mb-6 p-4 bg-red-900/30 border border-red-700 rounded-lg text-red-300 flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            {error}
          </div>
        )}

        {requiredFields.length > 0 && (
          <div className="mb-6 p-4 bg-yellow-900/30 border border-yellow-700 rounded-lg">
            <div className="flex items-center gap-2 text-yellow-300 mb-2">
              <AlertCircle className="w-5 h-5" />
              <span className="font-medium">Required Configuration Missing</span>
            </div>
            <ul className="text-sm text-yellow-200/70 list-disc list-inside">
              {requiredFields.map((field) => (
                <li key={field.path}>{field.display_name}</li>
              ))}
            </ul>
          </div>
        )}

        {currentIntegration && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <div className="flex items-center gap-4 mb-6">
              <div className="w-12 h-12 bg-slate-800 rounded-lg flex items-center justify-center">
                <span className="text-2xl">{currentIntegration.name[0]}</span>
              </div>
              <div>
                <h2 className="text-xl font-semibold text-white">
                  {currentIntegration.name}
                </h2>
                <p className="text-slate-400">{currentIntegration.description}</p>
              </div>
            </div>

            <div className="space-y-4">
              {currentIntegration.team_fields.map((field) => (
                <div key={field.name}>
                  <label className="block text-sm text-slate-400 mb-1.5">
                    {field.display_name}
                    {field.required && <span className="text-red-400 ml-1">*</span>}
                  </label>
                  {field.type === 'boolean' ? (
                    <label className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={
                          configValues[currentIntegration.id]?.[field.name] === 'true' ||
                          (configValues[currentIntegration.id]?.[field.name] === undefined && field.default === true)
                        }
                        onChange={(e) => updateFieldValue(currentIntegration.id, field.name, String(e.target.checked))}
                        className="w-4 h-4 rounded bg-slate-800 border-slate-600"
                      />
                      <span className="text-slate-300 text-sm">{field.description}</span>
                    </label>
                  ) : (
                    <>
                      <input
                        type={field.type === 'secret' ? 'password' : 'text'}
                        value={configValues[currentIntegration.id]?.[field.name] || ''}
                        onChange={(e) => updateFieldValue(currentIntegration.id, field.name, e.target.value)}
                        placeholder={field.placeholder || ''}
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                      />
                      {field.description && (
                        <p className="text-xs text-slate-500 mt-1">{field.description}</p>
                      )}
                    </>
                  )}
                </div>
              ))}
            </div>

            <div className="flex justify-between mt-8 pt-6 border-t border-slate-800">
              <button
                onClick={() => setStep(Math.max(0, step - 1))}
                disabled={step === 0}
                className="px-4 py-2 text-slate-400 hover:text-white disabled:opacity-50 transition-colors"
              >
                Back
              </button>
              <div className="flex gap-3">
                <button
                  onClick={() => {
                    if (step < COMMON_INTEGRATIONS.length - 1) {
                      setStep(step + 1);
                    } else {
                      loadRequiredFields();
                    }
                  }}
                  className="px-4 py-2 text-slate-400 hover:text-white transition-colors"
                >
                  Skip
                </button>
                <button
                  onClick={() => saveIntegrationConfig(currentIntegration.id)}
                  disabled={saving}
                  className="px-6 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                  {saving ? 'Saving...' : step < COMMON_INTEGRATIONS.length - 1 ? 'Save & Continue' : 'Complete Setup'}
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Help Link */}
        <div className="mt-8 text-center">
          <a
            href="https://docs.incidentfox.io/integrations"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-cyan-400 transition-colors"
          >
            <ExternalLink className="w-4 h-4" />
            Need help with integrations?
          </a>
        </div>
      </div>
    </div>
  );
}

