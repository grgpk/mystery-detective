"use client";

import type { Message } from "@ag-ui/client";
import { UseAgentUpdate, useAgent, useCopilotKit } from "@copilotkit/react-core/v2";
import { createContext, use, useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { useUi } from "@/lib/store";
import { isPublicState, type Board, type GameAction, type PublicState } from "@/lib/protocol/types";

const RUNTIME_AGENT_ID = "game_master";
const THREAD_STORAGE_KEY = "last-alibi:thread";
const BOARD_SYNC_DELAY_MS = 1500;
const AGENT_UPDATES = [
  UseAgentUpdate.OnMessagesChanged,
  UseAgentUpdate.OnStateChanged,
  UseAgentUpdate.OnRunStatusChanged,
];

interface GameContextValue {
  state: PublicState | null;
  messages: readonly Message[];
  isRunning: boolean;
  error: string | null;
  threadId: string;
  send: (action: GameAction, playerText?: string) => Promise<void>;
  updateBoard: (board: Board) => void;
  /** Starts a fresh thread; omit caseId for a random case. */
  newGame: (caseId?: string) => void;
}

const GameContext = createContext<GameContextValue | null>(null);

export function useGame(): GameContextValue {
  const value = use(GameContext);
  if (!value) throw new Error("useGame must be used inside <GameProvider>");
  return value;
}

function readThreadId(): string {
  try {
    const stored = window.localStorage.getItem(THREAD_STORAGE_KEY);
    if (stored) return stored;
  } catch {
    // Storage can be unavailable (private mode); a fresh thread just means a fresh case.
  }
  return storeThreadId(crypto.randomUUID());
}

function storeThreadId(threadId: string): string {
  try {
    window.localStorage.setItem(THREAD_STORAGE_KEY, threadId);
  } catch {
    // See readThreadId.
  }
  return threadId;
}

/** Client-only (rendered with ssr: false): owns the thread id, remounting the session for a new case. */
export function GameProvider({ children }: { children: ReactNode }) {
  const [game, setGame] = useState<{ threadId: string; caseId?: string }>(() => ({ threadId: readThreadId() }));
  const newGame = useCallback(
    (caseId?: string) => setGame({ threadId: storeThreadId(crypto.randomUUID()), caseId }),
    [],
  );
  return (
    <GameSession key={game.threadId} threadId={game.threadId} caseId={game.caseId} newGame={newGame}>
      {children}
    </GameSession>
  );
}

interface GameSessionProps {
  threadId: string;
  /** Case to open if this thread has no game yet; the agent ignores it for an existing game. */
  caseId?: string;
  newGame: (caseId?: string) => void;
  children: ReactNode;
}

function GameSession({ threadId, caseId, newGame, children }: GameSessionProps) {
  const { agent, isReady } = useAgent({
    agentId: `game-${threadId}`,
    runtimeAgentId: RUNTIME_AGENT_ID,
    threadId,
    updates: AGENT_UPDATES,
  });
  const { copilotkit } = useCopilotKit();
  const [error, setError] = useState<string | null>(null);
  const runError = useUi((s) => s.runError);
  const started = useRef(false);
  const boardTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const send = useCallback(
    async (action: GameAction, playerText?: string) => {
      if (agent.isRunning) return;
      if (boardTimer.current) clearTimeout(boardTimer.current); // this run carries the board in its state
      if (playerText) agent.addMessage({ id: crypto.randomUUID(), role: "user", content: playerText });
      setError(null);
      useUi.getState().setRunError(null);
      try {
        await copilotkit.runAgent({ agent, forwardedProps: { gameAction: action } });
      } catch (err) {
        setError(err instanceof Error ? err.message : "The line to the station went dead. Try again.");
      }
    },
    [agent, copilotkit],
  );

  useEffect(() => {
    if (!isReady || started.current) return;
    started.current = true;
    void send({ type: "start", caseId });
  }, [isReady, send, caseId]);

  useEffect(() => () => {
    if (boardTimer.current) clearTimeout(boardTimer.current);
  }, []);

  const state = isPublicState(agent.state) ? agent.state : null;

  const updateBoard = useCallback(
    (board: Board) => {
      if (!isPublicState(agent.state)) return;
      agent.setState({ ...agent.state, board });
      if (boardTimer.current) clearTimeout(boardTimer.current);
      boardTimer.current = setTimeout(() => {
        if (!agent.isRunning) void send({ type: "sync_board", board });
      }, BOARD_SYNC_DELAY_MS);
    },
    [agent, send],
  );

  // Built every render on purpose: useAgent re-renders this component on each message/state/run change,
  // and the agent may update its arrays in place, so memoizing on references could serve stale data.
  const value: GameContextValue = {
    state,
    messages: [...agent.messages],
    isRunning: agent.isRunning,
    error: error ?? runError,
    threadId,
    send,
    updateBoard,
    newGame,
  };

  return <GameContext value={value}>{children}</GameContext>;
}
