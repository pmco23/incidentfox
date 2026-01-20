import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Activity, Database, Globe, Lock, Server } from 'lucide-react';
import { clsx } from 'clsx';

const ServiceNode = ({ data, selected }: any) => {
  const Icon = {
    frontend: Globe,
    api: Server,
    auth: Lock,
    db: Database,
    service: Activity
  }[data.type as string] || Activity;

  return (
    <div className={clsx(
      "px-4 py-3 shadow-lg rounded-xl bg-white dark:bg-gray-900 border-2 transition-all min-w-[150px]",
      selected ? "border-orange-500 ring-4 ring-orange-500/20" : "border-gray-200 dark:border-gray-700",
      data.status === 'error' && !selected && "border-red-500 animate-pulse",
      data.status === 'warning' && !selected && "border-yellow-500"
    )}>
      <div className="flex items-center gap-3">
        <div className={clsx(
          "w-8 h-8 rounded-full flex items-center justify-center",
          data.status === 'error' ? "bg-red-100 text-red-600" : 
          data.status === 'warning' ? "bg-yellow-100 text-yellow-600" :
          "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
        )}>
          <Icon className="w-4 h-4" />
        </div>
        <div>
          <div className="text-xs font-bold text-gray-900 dark:text-white">{data.label}</div>
          <div className="text-[10px] text-gray-500">{data.requests} req/s</div>
        </div>
      </div>

      {/* Handles */}
      <Handle type="target" position={Position.Top} className="w-2 h-2 !bg-gray-400" />
      <Handle type="source" position={Position.Bottom} className="w-2 h-2 !bg-gray-400" />
    </div>
  );
};

export default memo(ServiceNode);

