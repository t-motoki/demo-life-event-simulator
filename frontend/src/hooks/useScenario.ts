import { useReducer, type Dispatch } from 'react';
import type { LifeEvent } from '../types/scenario';

// 操作の意図を reducer のアクション型で明示する
type EventAction =
  | { type: 'ADD'; event: LifeEvent }
  | { type: 'EDIT'; index: number; event: LifeEvent }
  | { type: 'DELETE'; index: number }
  | { type: 'SET_ALL'; events: LifeEvent[] };

function reducer(state: LifeEvent[], action: EventAction): LifeEvent[] {
  switch (action.type) {
    case 'ADD':
      return [...state, action.event];
    case 'EDIT':
      return state.map((e, i) => (i === action.index ? action.event : e));
    case 'DELETE':
      return state.filter((_, i) => i !== action.index);
    case 'SET_ALL':
      return action.events;
  }
}

interface UseScenarioReturn {
  events: LifeEvent[];
  dispatch: Dispatch<EventAction>;
}

export function useScenario(): UseScenarioReturn {
  const [events, dispatch] = useReducer(reducer, []);
  return { events, dispatch };
}
