import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../utils/format";

/**
 * Run an async loader whenever `deps` change.
 * Returns { data, error, loading, reload }. Stale responses are ignored.
 */
export function useAsync(loader, deps = [], { enabled = true } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled });
  const seq = useRef(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const run = useCallback(async () => {
    const id = ++seq.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await loaderRef.current();
      if (id === seq.current) setState({ data, error: null, loading: false });
    } catch (err) {
      if (id === seq.current) setState({ data: null, error: { message: errorMessage(err), status: err?.response?.status }, loading: false });
    }
  }, []);

  useEffect(() => {
    if (enabled) run();
    else setState({ data: null, error: null, loading: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, ...deps]);

  return { ...state, reload: run };
}
