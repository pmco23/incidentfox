'use client';

import { useState } from 'react';
import { Loader2, X, Database } from 'lucide-react';

interface CreateTreeModalProps {
  onClose: () => void;
  onCreated: (treeName: string) => void;
}

export function CreateTreeModal({ onClose, onCreated }: CreateTreeModalProps) {
  const [treeName, setTreeName] = useState('');
  const [description, setDescription] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isValidName = /^[a-zA-Z0-9_-]+$/.test(treeName);

  const handleCreate = async () => {
    if (!treeName || !isValidName) return;

    setCreating(true);
    setError(null);

    try {
      const res = await fetch('/api/team/knowledge/tree/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tree_name: treeName, description }),
      });

      if (res.ok) {
        onCreated(treeName);
        onClose();
      } else {
        const data = await res.json();
        setError(data.error || data.detail || 'Failed to create tree');
      }
    } catch (e) {
      setError('Failed to create tree');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-900 rounded-2xl w-full max-w-md p-6 shadow-xl">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-amber-500 flex items-center justify-center">
              <Database className="w-5 h-5 text-white" />
            </div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Create Knowledge Tree
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Tree Name
            </label>
            <input
              type="text"
              value={treeName}
              onChange={(e) => setTreeName(e.target.value)}
              placeholder="e.g., team-sre-runbooks"
              className={`w-full px-3 py-2 rounded-lg border bg-white dark:bg-gray-800 ${
                treeName && !isValidName
                  ? 'border-red-500 focus:ring-red-500'
                  : 'border-gray-200 dark:border-gray-700 focus:ring-orange-500'
              } focus:outline-none focus:ring-2`}
            />
            {treeName && !isValidName && (
              <p className="text-xs text-red-500 mt-1">
                Only letters, numbers, hyphens, and underscores allowed
              </p>
            )}
            <p className="text-xs text-gray-500 mt-1">
              This will be the unique identifier for your tree
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Description (optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder="What kind of knowledge will this tree contain?"
              className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-orange-500"
            />
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm">
              {error}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={!treeName || !isValidName || creating}
            className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {creating && <Loader2 className="w-4 h-4 animate-spin" />}
            {creating ? 'Creating...' : 'Create Tree'}
          </button>
        </div>
      </div>
    </div>
  );
}
