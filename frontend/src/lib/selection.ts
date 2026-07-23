export interface SelectionState {
  mode: boolean;
  ids: Set<string>;
}

export const emptySelection = (): SelectionState => ({
  mode: false,
  ids: new Set(),
});

export function toggleId(state: SelectionState, id: string): SelectionState {
  const ids = new Set(state.ids);
  if (ids.has(id)) ids.delete(id);
  else ids.add(id);
  return { ...state, ids };
}

export function selectAll(state: SelectionState, allIds: string[]): SelectionState {
  return { ...state, ids: new Set(allIds) };
}

export function clearSelection(state: SelectionState): SelectionState {
  return { ...state, ids: new Set() };
}

export function enterSelectMode(state: SelectionState): SelectionState {
  return { ...state, mode: true };
}

export function exitSelectMode(): SelectionState {
  return emptySelection();
}
