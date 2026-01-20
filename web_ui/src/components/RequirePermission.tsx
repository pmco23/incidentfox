'use client';

import Link from 'next/link';
import { useIdentity } from '@/lib/useIdentity';

function hasPerm(perms: string[] | undefined, required: string) {
  const s = new Set((perms || []).filter(Boolean));
  return s.has('admin:*') || s.has(required);
}

export function RequirePermission({
  permission,
  children,
  fallback,
}: {
  permission: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}) {
  const { identity, loading, error } = useIdentity();

  if (loading) return null;
  if (!identity) {
    return (
      fallback ?? (
        <div className="text-sm text-gray-600 dark:text-gray-300">
          Sign-in required. <Link href="/settings" className="underline">Sign in</Link>.
          {error ? <span className="text-red-600"> ({error})</span> : null}
        </div>
      )
    );
  }

  if (!hasPerm(identity.permissions, permission)) {
    return (
      fallback ?? (
        <div className="text-sm text-gray-600 dark:text-gray-300">
          Missing permission: <span className="font-mono">{permission}</span>
        </div>
      )
    );
  }

  return <>{children}</>;
}


