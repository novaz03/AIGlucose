'use client';

import {
  createContext,
  type ReactNode,
  useContext,
  useMemo,
  useState,
  useCallback
} from "react";

export type HeightUnit = "cm" | "ft";
export type WeightUnit = "kg" | "lb";

export type UserMetrics = {
  age: number | null;
  height: number | null;
  weight: number | null;
  gender: string | null;
  heightUnit: HeightUnit;
  weightUnit: WeightUnit;
  a1c: number | null;
  underlyingDisease: string | null;
};

type UserContextValue = {
  metrics: UserMetrics;
  updateMetrics: (updates: Partial<UserMetrics>) => void;
};

const UserContext = createContext<UserContextValue | undefined>(undefined);

export function UserProvider({ children }: { children: ReactNode }) {
  const [metrics, setMetrics] = useState<UserMetrics>({
    age: null,
    height: null,
    weight: null,
    gender: null,
    heightUnit: "cm",
    weightUnit: "kg",
    a1c: null,
    underlyingDisease: null
  });

  const updateMetrics = useCallback((updates: Partial<UserMetrics>) => {
    setMetrics((current) => ({
      ...current,
      ...updates
    }));
  }, []);

  const value = useMemo(
    () => ({
      metrics,
      updateMetrics
    }),
    [metrics, updateMetrics]
  );

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

export function useUser() {
  const context = useContext(UserContext);

  if (!context) {
    throw new Error("useUser must be used within a UserProvider");
  }

  return context;
}
