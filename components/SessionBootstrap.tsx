'use client';

import { useEffect } from 'react';
import { getSession, fetchProfile } from '@/lib/api';
import { useUser } from '@/context/UserContext';

export default function SessionBootstrap() {
  const { updateMetrics } = useUser();

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      try {
        await getSession();
      } catch {
        return; // Not logged in; nothing to bootstrap
      }

      try {
        const profile = await fetchProfile();
        if (cancelled) return;
        updateMetrics({
          age: typeof profile.age === 'number' ? profile.age : null,
          height: typeof profile.height_cm === 'number' ? profile.height_cm : null,
          weight: typeof profile.weight_kg === 'number' ? profile.weight_kg : null,
          underlyingDisease: profile.underlying_disease ?? null,
          gender: typeof (profile as any).gender === 'string' ? (profile as any).gender : null,
        });
      } catch {
        // ignore; profile will be pulled by specific pages as needed
      }
    };

    run();
    return () => {
      cancelled = true;
    };
  }, [updateMetrics]);

  return null;
}

