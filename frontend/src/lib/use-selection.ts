"use client";

import { useCallback, useState } from "react";
import {
  clearSelection,
  emptySelection,
  enterSelectMode,
  exitSelectMode,
  selectAll,
  toggleId,
  type SelectionState,
} from "./selection";

export function useSelection() {
  const [state, setState] = useState<SelectionState>(emptySelection);
  return {
    mode: state.mode,
    selected: state.ids,
    count: state.ids.size,
    isSelected: (id: string) => state.ids.has(id),
    toggle: useCallback((id: string) => setState((s) => toggleId(s, id)), []),
    selectAll: useCallback((ids: string[]) => setState((s) => selectAll(s, ids)), []),
    clear: useCallback(() => setState((s) => clearSelection(s)), []),
    enter: useCallback(() => setState((s) => enterSelectMode(s)), []),
    exit: useCallback(() => setState(exitSelectMode()), []),
  };
}
