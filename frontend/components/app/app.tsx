'use client';

import {
  RoomAudioRenderer,
  StartAudio,
  useConnectionState,
  useDataChannel,
  useRoomContext,
} from '@livekit/components-react';

import { ConnectionState } from 'livekit-client';
import type { AppConfig } from '@/app-config';
import { SessionProvider } from '@/components/app/session-provider';
import { ViewController } from '@/components/app/view-controller';
import { Toaster } from '@/components/livekit/toaster';
import { useState } from 'react';

interface AppProps {
  appConfig: AppConfig;
}

/* -----------------------
   1. GAME STATE HANDLER
------------------------- */

type GameState = {
  player: {
    hp: number;
    max_hp: number;
    ram: number;
    max_ram: number;
    status: string;
    inventory: string[];
  };
  world: {
    location: string;
    danger_level: string;
  };
  log: string[];
};

const useGameState = () => {
  const [state, setState] = useState<GameState>({
    player: {
      hp: 100,
      max_hp: 100,
      ram: 80,
      max_ram: 100,
      status: 'Calm',
      inventory: ['Wooden Charm', 'Forest Map', 'Water Flask'],
    },
    world: {
      location: 'Forest Edge',
      danger_level: 'Low',
    },
    log: [],
  });

  useDataChannel("game_state_update", (msg) => {
    try {
      const raw = msg.payload;
      if (!raw) return;

      const json = JSON.parse(new TextDecoder().decode(raw));
      setState(json as GameState);
    } catch (err) {
      console.error("DataChannel JSON Parse Error:", err);
    }
  });

  const room = useRoomContext();
  return { state, room };
};

/* -----------------------
       Magical Glow Overlay
------------------------- */

const ForestOverlay = () => (
  <div className="pointer-events-none absolute inset-0 z-30 opacity-40">
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_30%,rgba(0,255,127,0.15),transparent_60%)]" />
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_80%,rgba(173,216,230,0.18),transparent_70%)]" />
  </div>
);

/* -----------------------
          Header
------------------------- */

const ForestHeader = () => {
  const state = useConnectionState();
  const connected = state === ConnectionState.Connected;

  return (
    <header className="border-b border-emerald-900/40 bg-green-950/80 px-6 py-3 flex justify-between items-center text-emerald-200 font-mono shadow-[0_0_20px_rgba(0,255,127,0.25)] z-20 relative">
      <div className="flex items-center gap-3">
        <div
          className={`w-3 h-3 rounded-full ${
            connected ? 'bg-emerald-400 shadow-[0_0_10px_rgba(0,255,127,0.9)]' : 'bg-emerald-900'
          }`}
        ></div>
        <div className="text-xl md:text-2xl font-black tracking-[0.2em] text-emerald-300">
          FOREST REALM
        </div>
      </div>

      <div className="flex items-center gap-4 text-xs border border-emerald-900/60 px-3 py-1 rounded bg-emerald-900/20 backdrop-blur-sm">
        <span className="opacity-70 text-emerald-300">LINK:</span>
        <span
          className={`${
            connected ? 'text-green-200' : 'text-red-400'
          } font-semibold tracking-widest`}
        >
          {connected ? 'AERIS_ONLINE' : `${state}`.toUpperCase()}
        </span>
      </div>
    </header>
  );
};

/* -----------------------
       Explorer HUD
------------------------- */

const ExplorerHUD = ({ state }: { state: GameState }) => {
  const hpPercent = (state.player.hp / state.player.max_hp) * 100;
  const energyPercent = (state.player.ram / state.player.max_ram) * 100;

  return (
    <div className="h-full w-full rounded-2xl border border-emerald-900/60 bg-gradient-to-br from-emerald-950/70 via-green-950/70 to-emerald-800/40 p-4 md:p-5 flex flex-col gap-4 shadow-[0_0_20px_rgba(0,0,0,0.75)]">
      <div className="flex items-center justify-between">
        <h2 className="text-xs uppercase tracking-widest text-emerald-300">Explorer Status</h2>
        <span className="text-[0.7rem] text-emerald-400/60">ID: TRV-1</span>
      </div>

      {/* HP / Energy Bars */}
      <div className="space-y-3">
        <div>
          <div className="flex justify-between text-[0.7rem] mb-1 text-emerald-200/80">
            <span>Vitality</span>
            <span>
              {state.player.hp}/{state.player.max_hp}
            </span>
          </div>
          <div className="w-full h-2 rounded-full bg-green-900/40 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-green-300 to-yellow-200 transition-all"
              style={{ width: `${hpPercent}%` }}
            />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-[0.7rem] mb-1 text-blue-100/80">
            <span>Focus Energy</span>
            <span>
              {state.player.ram}/{state.player.max_ram}
            </span>
          </div>
          <div className="w-full h-2 rounded-full bg-sky-900/40 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-sky-300 to-indigo-300 transition-all"
              style={{ width: `${energyPercent}%` }}
            />
          </div>
        </div>
      </div>

      {/* Status + Location */}
      <div className="grid grid-cols-2 gap-3 text-[0.75rem] mt-1">
        <div className="border border-emerald-800 rounded-lg p-2 bg-green-950/40">
          <div className="text-[0.6rem] text-emerald-400/70 mb-1">Spiritual State</div>
          <div className="text-xs text-emerald-100">{state.player.status}</div>
        </div>

        <div className="border border-teal-900 rounded-lg p-2 bg-green-950/40">
          <div className="text-[0.6rem] text-teal-300/70 mb-1">Location</div>
          <div className="text-xs text-teal-100">{state.world.location}</div>
          <div className="text-[0.6rem] text-teal-300/50">
            Calmness: {state.world.danger_level}
          </div>
        </div>
      </div>

      {/* Inventory */}
      <div className="mt-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[0.75rem] text-amber-200/80">Items</span>
          <span className="text-[0.6rem] text-amber-300/60">
            {state.player.inventory.length} items
          </span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {state.player.inventory.map((item) => (
            <span
              key={item}
              className="text-[0.65rem] border border-amber-400/50 rounded-full px-2 py-0.5 bg-green-950/40 text-amber-100"
            >
              {item}
            </span>
          ))}
        </div>
      </div>

      {/* Log */}
      {state.log.length > 0 && (
        <div className="mt-3 border-t border-green-900/40 pt-2">
          <div className="text-[0.6rem] text-teal-300 mb-1">Recent Notes</div>
          <div className="space-y-1 max-h-24 overflow-y-auto text-[0.65rem] text-emerald-50">
            {state.log.slice(-5).map((entry, i) => (
              <div key={i} className="leading-snug">
                ▸ {entry}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

/* -----------------------
       GAME DASHBOARD
------------------------- */

const GameDashboard = () => {
  const { state } = useGameState();

  return (
    <div className="flex flex-col h-full w-full absolute inset-0 z-10 pointer-events-auto">
      <ForestHeader />

      <div className="flex flex-1 overflow-hidden relative p-4 md:p-6">
        <div className="grid grid-cols-1 lg:grid-cols-[0.7fr_1.3fr] gap-4 w-full">

          {/* HUD */}
          <div className="min-h-[260px]">
            <ExplorerHUD state={state} />
          </div>

          {/* GM Window */}
          <div className="rounded-2xl border border-green-900/60 bg-green-950/80 shadow-[0_0_30px_rgba(0,0,0,0.85)] relative overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-4 py-2 border-b border-green-900/60 bg-green-950/50 text-xs text-green-200 font-mono">
              <span>FOREST GUIDE // AERIS</span>
              <span className="text-[0.6rem] opacity-70">VOICE-ONLY CHANNEL</span>
            </div>

            {/* placeholder */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-20">
              <div className="text-sm font-black tracking-widest text-green-300/80">
                NO_VISUAL_FEED
              </div>
              <div className="text-[0.6rem] text-green-200/70 mt-1">
                AUDIO LINK ACTIVE
              </div>
            </div>

            <div className="relative flex-1 bg-black">
              <ViewController />
            </div>
          </div>
        </div>

        {/* Mobile mini-view */}
        <div className="lg:hidden fixed bottom-6 right-4 w-28 h-28 z-20 border border-green-500/50 rounded-2xl overflow-hidden bg-green-950/80 shadow-[0_0_20px_rgba(0,255,127,0.3)]">
          <ViewController />
        </div>
      </div>
    </div>
  );
};

/* -----------------------
            ROOT
------------------------- */

export function App({ appConfig }: AppProps) {
  return (
    <SessionProvider appConfig={appConfig}>
      <div className="relative h-svh w-full overflow-hidden bg-green-950 text-emerald-100 font-mono">

        <div className="absolute inset-0 bg-gradient-to-br from-green-950 via-emerald-900 to-lime-900/30" />
        <div className="absolute inset-0 opacity-25 bg-[radial-gradient(circle_at_20%_20%,rgba(34,197,94,0.2),transparent_60%)]" />
        <div className="absolute inset-0 opacity-10 bg-[repeating-linear-gradient(90deg,rgba(6,95,70,0.4)_0,rgba(6,95,70,0.4)_1px,transparent_1px,transparent_4px)]" />

        <ForestOverlay />
        <GameDashboard />
      </div>

      <StartAudio label="Begin Journey" />
      <RoomAudioRenderer />
      <Toaster />
    </SessionProvider>
  );
}
