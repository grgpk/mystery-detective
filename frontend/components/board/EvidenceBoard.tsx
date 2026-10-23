"use client";

import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  applyNodeChanges,
  type Connection,
  type Edge,
  type Node,
  type NodeChange,
  type NodeProps,
} from "@xyflow/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useGame } from "@/lib/game-context";
import type { Board, PublicState } from "@/lib/protocol/types";

type XY = { x: number; y: number };
// React Flow writes measured sizes back through onNodesChange; nodes stay hidden until we keep them.
type Layout = Record<string, { position: XY; measured?: CardNode["measured"] }>;
type CardData = { title: string; text: string; kind: "clue" | "statement"; onUnpin: () => void };
type CardNode = Node<CardData, "card">;

const POSITIONS_KEY = "last-alibi:board-positions:";
const STRING_STYLE = { stroke: "var(--string)", strokeWidth: 2 };

function loadPositions(threadId: string): Record<string, XY> {
  try {
    return JSON.parse(window.localStorage.getItem(POSITIONS_KEY + threadId) ?? "{}");
  } catch {
    return {};
  }
}

function savePositions(threadId: string, positions: Record<string, XY>) {
  try {
    window.localStorage.setItem(POSITIONS_KEY + threadId, JSON.stringify(positions));
  } catch {
    // Positions are a convenience; losing them only re-grids the board.
  }
}

function defaultPosition(index: number): XY {
  return { x: 20 + (index % 2) * 190, y: 20 + Math.floor(index / 2) * 130 };
}

function describe(state: PublicState, id: string): Omit<CardData, "onUnpin"> | null {
  const clue = state.clues.find((c) => c.id === id);
  if (clue) return { title: clue.title, text: clue.text, kind: "clue" };
  const statement = state.statements.find((s) => s.id === id);
  if (!statement) return null;
  const speaker = state.suspects.find((s) => s.id === statement.suspect)?.name ?? "Unknown";
  return { title: speaker, text: `“${statement.text}”`, kind: "statement" };
}

function CardNodeView({ data }: NodeProps<CardNode>) {
  return (
    <div className={`paper w-44 rounded-sm p-2 text-xs ${data.kind === "statement" ? "rotate-1" : "-rotate-1"}`}>
      <Handle type="target" position={Position.Top} className="!bg-string" />
      <div className="flex items-start justify-between gap-1">
        <p className="font-type text-[11px] leading-tight uppercase">{data.title}</p>
        <button
          type="button"
          onClick={data.onUnpin}
          className="nodrag text-ink-soft hover:text-string -mt-0.5 px-1"
          aria-label={`Unpin ${data.title}`}
        >
          ×
        </button>
      </div>
      <p className="text-ink-soft mt-1 line-clamp-4 leading-snug">{data.text}</p>
      <Handle type="source" position={Position.Bottom} className="!bg-string" />
    </div>
  );
}

const NODE_TYPES = { card: CardNodeView };

function withLink(board: Board, from: string, to: string): Board {
  const exists = board.links.some((l) => (l.from === from && l.to === to) || (l.from === to && l.to === from));
  const pins = [...new Set([...board.pins, from, to])];
  return { ...board, pins, links: exists ? board.links : [...board.links, { from, to }] };
}

export function EvidenceBoard() {
  const { state, updateBoard, threadId } = useGame();
  const [layout, setLayout] = useState<Layout>(() =>
    Object.fromEntries(Object.entries(loadPositions(threadId)).map(([id, position]) => [id, { position }])),
  );
  const board = state?.board;

  // A successful confrontation strings the two cards together.
  const contradiction = state?.lastContradiction;
  useEffect(() => {
    if (!contradiction || !board) return;
    const next = withLink(board, contradiction.from, contradiction.to);
    if (next.links.length !== board.links.length || next.pins.length !== board.pins.length) updateBoard(next);
  }, [contradiction, board, updateBoard]);

  const unpin = useCallback(
    (id: string) => {
      if (!board) return;
      updateBoard({
        ...board,
        pins: board.pins.filter((p) => p !== id),
        links: board.links.filter((l) => l.from !== id && l.to !== id),
      });
    },
    [board, updateBoard],
  );

  const nodes = useMemo<CardNode[]>(() => {
    if (!state || !board) return [];
    return board.pins.flatMap((id, index) => {
      const card = describe(state, id);
      if (!card) return [];
      return [
        {
          id,
          type: "card",
          position: layout[id]?.position ?? defaultPosition(index),
          measured: layout[id]?.measured,
          data: { ...card, onUnpin: () => unpin(id) },
        },
      ];
    });
  }, [state, board, layout, unpin]);

  const edges = useMemo<Edge[]>(() => {
    if (!board) return [];
    return board.links.map((link) => {
      const fresh =
        contradiction &&
        ((contradiction.from === link.from && contradiction.to === link.to) ||
          (contradiction.from === link.to && contradiction.to === link.from));
      return {
        id: `${link.from}->${link.to}`,
        source: link.from,
        target: link.to,
        animated: Boolean(fresh),
        label: fresh ? "Contradiction!" : undefined,
        labelStyle: { fill: "var(--string)", fontFamily: "var(--font-typewriter)" },
        style: STRING_STYLE,
      };
    });
  }, [board, contradiction]);

  const onNodesChange = useCallback(
    (changes: NodeChange<CardNode>[]) => {
      const next = applyNodeChanges(changes, nodes);
      setLayout(Object.fromEntries(next.map((n) => [n.id, { position: n.position, measured: n.measured }])));
      if (changes.some((c) => c.type === "position" && !c.dragging)) {
        savePositions(threadId, Object.fromEntries(next.map((n) => [n.id, n.position])));
      }
    },
    [nodes, threadId],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      if (board && connection.source && connection.target && connection.source !== connection.target) {
        updateBoard(withLink(board, connection.source, connection.target));
      }
    },
    [board, updateBoard],
  );

  const onEdgesDelete = useCallback(
    (deleted: Edge[]) => {
      if (!board) return;
      const gone = new Set(deleted.map((e) => e.id));
      updateBoard({ ...board, links: board.links.filter((l) => !gone.has(`${l.from}->${l.to}`)) });
    },
    [board, updateBoard],
  );

  if (!state || !board) return null;
  const unpinned = [
    ...state.clues.filter((c) => !board.pins.includes(c.id)).map((c) => ({ id: c.id, label: c.title })),
    ...state.statements
      .filter((s) => !board.pins.includes(s.id))
      .map((s) => ({
        id: s.id,
        label: `${state.suspects.find((p) => p.id === s.suspect)?.name.split(" ").at(-1)}: “${s.text}”`,
      })),
  ];

  return (
    <section aria-labelledby="board-heading" className="grid gap-3">
      <h2 id="board-heading" className="font-type text-on-desk-soft text-sm tracking-[0.2em] uppercase">
        Evidence board
      </h2>
      <div className="h-80 overflow-hidden rounded-sm border border-[#5a4632] bg-[#3b2d21] sm:h-96">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          onNodesChange={onNodesChange}
          onConnect={onConnect}
          onEdgesDelete={onEdgesDelete}
          fitView
          minZoom={0.4}
          maxZoom={1.5}
          aria-label="Evidence board: drag from a card's bottom pin to another card to link them with red string"
        >
          <Background color="#5a4632" gap={22} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      {unpinned.length > 0 && (
        <details className="text-sm">
          <summary className="text-on-desk-soft cursor-pointer">Unpinned evidence ({unpinned.length})</summary>
          <ul className="mt-2 grid gap-1">
            {unpinned.map((item) => (
              <li key={item.id} className="flex items-start justify-between gap-2">
                <span className="text-on-desk-soft">{item.label}</span>
                <button
                  type="button"
                  className="text-brass font-type shrink-0 text-xs uppercase hover:underline"
                  onClick={() => updateBoard({ ...board, pins: [...board.pins, item.id] })}
                >
                  Pin
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}

      <label className="grid gap-1 text-sm">
        <span className="font-type text-on-desk-soft text-xs uppercase">Notes</span>
        <textarea
          value={board.notes}
          onChange={(e) => updateBoard({ ...board, notes: e.target.value })}
          rows={4}
          maxLength={4000}
          placeholder="Henry lied about the garden?"
          className="bg-paper text-ink rounded-sm p-2 font-serif"
        />
      </label>
    </section>
  );
}
