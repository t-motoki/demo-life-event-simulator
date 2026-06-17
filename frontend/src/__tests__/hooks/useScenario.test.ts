import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useScenario } from '../../hooks/useScenario';
import type { LifeEvent } from '../../types/scenario';

const makeMarriage = (year: number): LifeEvent => ({
  type: 'marriage',
  year,
  cost: 3000000,
});

describe('useScenario - SET_ALL', () => {
  it('SET_ALL でイベント一覧が差し替わる', () => {
    const { result } = renderHook(() => useScenario());

    // 既存イベント2件を追加
    act(() => {
      result.current.dispatch({ type: 'ADD', event: makeMarriage(2027) });
    });
    act(() => {
      result.current.dispatch({ type: 'ADD', event: makeMarriage(2028) });
    });
    expect(result.current.events).toHaveLength(2);

    // SET_ALL で新しい3件に差し替え
    const newEvents: LifeEvent[] = [
      makeMarriage(2030),
      makeMarriage(2031),
      makeMarriage(2032),
    ];
    act(() => {
      result.current.dispatch({ type: 'SET_ALL', events: newEvents });
    });
    expect(result.current.events).toHaveLength(3);
    expect(result.current.events).toEqual(newEvents);
  });

  it('SET_ALL で空配列を渡すとイベントが全てクリアされる', () => {
    const { result } = renderHook(() => useScenario());

    act(() => {
      result.current.dispatch({ type: 'ADD', event: makeMarriage(2027) });
    });
    act(() => {
      result.current.dispatch({ type: 'ADD', event: makeMarriage(2028) });
    });
    expect(result.current.events).toHaveLength(2);

    act(() => {
      result.current.dispatch({ type: 'SET_ALL', events: [] });
    });
    expect(result.current.events).toEqual([]);
  });

  it('SET_ALL 後も ADD/EDIT/DELETE が正常に動作する', () => {
    const { result } = renderHook(() => useScenario());

    const newEvents: LifeEvent[] = [makeMarriage(2030), makeMarriage(2031)];
    act(() => {
      result.current.dispatch({ type: 'SET_ALL', events: newEvents });
    });
    expect(result.current.events).toHaveLength(2);

    act(() => {
      result.current.dispatch({ type: 'ADD', event: makeMarriage(2032) });
    });
    expect(result.current.events).toHaveLength(3);
  });
});
