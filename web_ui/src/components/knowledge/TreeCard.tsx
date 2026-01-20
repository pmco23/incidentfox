'use client';

import { Database, GitBranch, Layers } from 'lucide-react';

export interface TreeCardProps {
  treeName: string;
  level: string; // "org" | "group" | "team"
  nodeName: string;
  nodeId: string;
  inherited: boolean;
  isSelected: boolean;
  stats?: { nodes: number; layers: number };
  onSelect: () => void;
}

export function TreeCard({
  treeName,
  level,
  nodeName,
  inherited,
  isSelected,
  stats,
  onSelect,
}: TreeCardProps) {
  const levelColors: Record<string, string> = {
    org: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
    group: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400',
    team: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
  };

  return (
    <button
      onClick={onSelect}
      className={`
        w-full text-left p-4 rounded-xl border transition-all
        ${
          isSelected
            ? 'border-orange-500 bg-orange-50 dark:bg-orange-900/20 ring-2 ring-orange-500/30'
            : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 hover:border-gray-300 dark:hover:border-gray-600'
        }
      `}
    >
      <div className="flex items-start gap-3">
        <div
          className={`
            w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0
            ${isSelected ? 'bg-orange-500 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'}
          `}
        >
          <Database className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            {inherited && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500">
                Inherited
              </span>
            )}
            <span className={`text-xs px-1.5 py-0.5 rounded capitalize ${levelColors[level] || levelColors.team}`}>
              {level}
            </span>
          </div>
          <h3 className="font-medium text-gray-900 dark:text-white truncate">{treeName}</h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
            From {nodeName}
          </p>
          {stats && (
            <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
              <span className="flex items-center gap-1">
                <GitBranch className="w-3 h-3" />
                {stats.nodes.toLocaleString()} nodes
              </span>
              <span className="flex items-center gap-1">
                <Layers className="w-3 h-3" />
                {stats.layers} layers
              </span>
            </div>
          )}
        </div>
      </div>
    </button>
  );
}
