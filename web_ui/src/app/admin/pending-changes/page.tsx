'use client';

import { useEffect, useState, useCallback } from 'react';
import { useIdentity } from '@/lib/useIdentity';
import { apiFetch } from '@/lib/apiClient';
import { 
  Clock, 
  CheckCircle, 
  XCircle,
  AlertTriangle,
  RefreshCcw,
  FileText,
  Wrench,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

interface PendingChange {
  id: string;
  org_id: string;
  node_id: string;
  change_type: string;
  change_path: string | null;
  proposed_value: any;
  previous_value: any;
  requested_by: string;
  requested_at: string;
  reason: string | null;
  status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_comment: string | null;
}

export default function PendingChangesPage() {
  const { identity, loading: identityLoading } = useIdentity();
  const [changes, setChanges] = useState<PendingChange[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('pending');
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [reviewComment, setReviewComment] = useState('');

  const orgId = identity?.org_id || 'org1';
  const isAdmin = identity?.role === 'admin';

  const loadChanges = useCallback(async () => {
    if (!isAdmin) return;
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set('status', statusFilter);
      params.set('limit', '100');
      
      const res = await apiFetch(`/api/admin/orgs/${orgId}/pending-changes?${params}`);
      if (res.ok) {
        const data = await res.json();
        setChanges(data.items || []);
      }
    } catch (e) {
      console.error('Failed to load pending changes', e);
    } finally {
      setLoading(false);
    }
  }, [orgId, isAdmin, statusFilter]);

  useEffect(() => {
    if (isAdmin) {
      loadChanges();
    }
  }, [isAdmin, loadChanges]);

  const handleReview = async (changeId: string, action: 'approve' | 'reject') => {
    setReviewingId(changeId);
    try {
      const res = await apiFetch(`/api/admin/orgs/${orgId}/pending-changes/${changeId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, comment: reviewComment }),
      });
      if (res.ok) {
        setReviewComment('');
        loadChanges();
      } else {
        const err = await res.json();
        alert(err.detail || 'Review failed');
      }
    } catch (e: any) {
      alert(e?.message || 'Review failed');
    } finally {
      setReviewingId(null);
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const getChangeIcon = (type: string) => {
    switch (type) {
      case 'prompt':
        return <FileText className="w-5 h-5 text-gray-500" />;
      case 'tools':
        return <Wrench className="w-5 h-5 text-gray-500" />;
      default:
        return <AlertTriangle className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pending':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400">
            <Clock className="w-3 h-3" /> Pending
          </span>
        );
      case 'approved':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
            <CheckCircle className="w-3 h-3" /> Approved
          </span>
        );
      case 'rejected':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">
            <XCircle className="w-3 h-3" /> Rejected
          </span>
        );
      default:
        return null;
    }
  };

  if (identityLoading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <div className="animate-pulse text-gray-500">Loading...</div>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="p-8">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-6 text-center">
          <p className="text-red-600 dark:text-red-400">Admin access required</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Pending Changes</h1>
          <p className="text-sm text-gray-500 mt-1">
            Review and approve configuration changes that require admin approval.
          </p>
        </div>
        <button
          onClick={loadChanges}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700"
        >
          <RefreshCcw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="mb-6 flex gap-2">
        {['pending', 'approved', 'rejected', ''].map((status) => (
          <button
            key={status || 'all'}
            onClick={() => setStatusFilter(status)}
            className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
              statusFilter === status
                ? 'bg-orange-500 text-white'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
            }`}
          >
            {status === '' ? 'All' : status.charAt(0).toUpperCase() + status.slice(1)}
          </button>
        ))}
      </div>

      {/* Changes List */}
      {loading && changes.length === 0 ? (
        <div className="text-center py-12 text-gray-500">Loading changes...</div>
      ) : changes.length === 0 ? (
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-12 text-center">
          <Clock className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-500">No {statusFilter || ''} changes found</p>
        </div>
      ) : (
        <div className="space-y-4">
          {changes.map((change) => (
            <div
              key={change.id}
              className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden shadow-sm"
            >
              {/* Header */}
              <div
                className="p-4 flex items-center justify-between cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50"
                onClick={() => setExpandedId(expandedId === change.id ? null : change.id)}
              >
                <div className="flex items-center gap-3">
                  {getChangeIcon(change.change_type)}
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900 dark:text-white">
                        {change.change_type === 'prompt' ? 'Custom Prompt' : 
                         change.change_type === 'tools' ? 'Tool Enablement' : 
                         change.change_type}
                      </span>
                      {getStatusBadge(change.status)}
                    </div>
                    <div className="text-sm text-gray-500">
                      {change.node_id} • Requested by {change.requested_by} • {formatDate(change.requested_at)}
                    </div>
                  </div>
                </div>
                {expandedId === change.id ? (
                  <ChevronUp className="w-5 h-5 text-gray-400" />
                ) : (
                  <ChevronDown className="w-5 h-5 text-gray-400" />
                )}
              </div>

              {/* Expanded Content */}
              {expandedId === change.id && (
                <div className="border-t border-gray-200 dark:border-gray-800 p-4 space-y-4">
                  {/* Change Details */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1">Previous Value</label>
                      <pre className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg text-xs font-mono overflow-auto max-h-40">
                        {JSON.stringify(change.previous_value, null, 2) || 'null'}
                      </pre>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1">Proposed Value</label>
                      <pre className="p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg text-xs font-mono overflow-auto max-h-40">
                        {JSON.stringify(change.proposed_value, null, 2) || 'null'}
                      </pre>
                    </div>
                  </div>

                  {change.reason && (
                    <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1">Reason</label>
                      <p className="text-sm text-gray-700 dark:text-gray-300">{change.reason}</p>
                    </div>
                  )}

                  {/* Review Actions */}
                  {change.status === 'pending' && (
                    <div className="pt-4 border-t border-gray-200 dark:border-gray-800">
                      <label className="block text-xs font-medium text-gray-500 mb-2">Review Comment (optional)</label>
                      <textarea
                        value={expandedId === change.id ? reviewComment : ''}
                        onChange={(e) => setReviewComment(e.target.value)}
                        placeholder="Add a comment..."
                        rows={2}
                        className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm mb-3"
                      />
                      <div className="flex gap-3">
                        <button
                          onClick={() => handleReview(change.id, 'approve')}
                          disabled={reviewingId === change.id}
                          className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                        >
                          <CheckCircle className="w-4 h-4" />
                          {reviewingId === change.id ? 'Approving...' : 'Approve & Apply'}
                        </button>
                        <button
                          onClick={() => handleReview(change.id, 'reject')}
                          disabled={reviewingId === change.id}
                          className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                        >
                          <XCircle className="w-4 h-4" />
                          {reviewingId === change.id ? 'Rejecting...' : 'Reject'}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Review Result */}
                  {change.status !== 'pending' && change.reviewed_by && (
                    <div className="pt-4 border-t border-gray-200 dark:border-gray-800">
                      <div className="text-sm">
                        <span className="text-gray-500">Reviewed by </span>
                        <span className="font-medium text-gray-900 dark:text-white">{change.reviewed_by}</span>
                        <span className="text-gray-500"> on </span>
                        <span className="text-gray-900 dark:text-white">{change.reviewed_at ? formatDate(change.reviewed_at) : 'N/A'}</span>
                      </div>
                      {change.review_comment && (
                        <p className="mt-2 text-sm text-gray-600 dark:text-gray-400 italic">"{change.review_comment}"</p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

