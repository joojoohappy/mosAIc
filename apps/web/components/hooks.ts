"use client";
import { useCallback, useEffect, useState } from "react";
export function useApiData<T>(id: string, loader: (id: string) => Promise<T>) {
  const [state, setState] = useState<{
    data?: T;
    error?: unknown;
    loading: boolean;
  }>({ loading: true });
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let active = true;
    setState({ loading: true });
    loader(id)
      .then((data) => {
        if (active) setState({ data, loading: false });
      })
      .catch((error) => {
        if (active) setState({ error, loading: false });
      });
    return () => {
      active = false;
    };
  }, [id, loader, version]);
  const retry = useCallback(() => setVersion((v) => v + 1), []);
  return { ...state, retry };
}
export function useFavorites() {
  const [ids, setIds] = useState<string[]>([]);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    try {
      const stored: unknown = JSON.parse(
        localStorage.getItem("mosaic-favorites-v1") || "[]",
      );
      if (Array.isArray(stored))
        setIds(stored.filter((id): id is string => typeof id === "string"));
    } catch {}
    setReady(true);
  }, []);
  function toggle(id: string) {
    setIds((current) => {
      const next = current.includes(id)
        ? current.filter((i) => i !== id)
        : [...current, id];
      try {
        localStorage.setItem("mosaic-favorites-v1", JSON.stringify(next));
      } catch {}
      return next;
    });
  }
  return { ids, toggle, ready };
}
