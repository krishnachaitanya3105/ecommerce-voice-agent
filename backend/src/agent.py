# IMPROVE THE AGENT AS PER YOUR NEED 1
"""
Day 8 – Voice Game Master (Forest Beacon Adventure) - Voice-only GM agent

- Theme: Calm, magical forest exploration.
- GM Persona: "Aeris," a gentle forest guide who speaks softly and encourages exploration.
- Tools: Same core tools (start_adventure, get_scene, player_action, show_journal, restart_adventure).
- Userdata: Tracks simple items (Map, Charm, Water), notes, choices made, and current location.
- Goal: Guide the player through a peaceful forest journey to reach and activate the ancient Beacon Tree.
"""

import json
import logging
import os
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Annotated

from dotenv import load_dotenv
from pydantic import Field
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
    RunContext,
)

from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# -------------------------
# Logging
# -------------------------
logger = logging.getLogger("forest_beacon_agent")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)

load_dotenv(".env.local")

# -------------------------
# Forest Beacon World Definition
# -------------------------
WORLD = {
    "intro": {
        "title": "Forest Edge",
        "desc": (
            "You awaken on the edge of a quiet forest. Soft morning light spills through tall trees. "
            "In the distance, a gentle blue glow pulses between the branches. Your small travel bag "
            "rests beside you in the dew-covered grass."
        ),
        "choices": {
            "check_bag": {
                "desc": "Check your travel bag.",
                "result_scene": "bag_check",
            },
            "follow_light": {
                "desc": "Walk toward the faint blue glow.",
                "result_scene": "forest_path",
            },
            "look_around": {
                "desc": "Look around the forest edge.",
                "result_scene": "clearing",
            },
        },
    },

    "bag_check": {
        "title": "Travel Bag",
        "desc": (
            "Inside your bag you find a water flask, a folded paper map, and a small wooden charm "
            "engraved with a tree symbol. A gentle breeze rustles the leaves overhead."
        ),
        "choices": {
            "take_map": {
                "desc": "Take the paper map.",
                "result_scene": "forest_path",
                "effects": {"add_inventory": "Forest Map"},
            },
            "take_charm": {
                "desc": "Hold the wooden charm.",
                "result_scene": "clearing",
                "effects": {"add_inventory": "Wooden Charm"},
            },
        },
    },

    "clearing": {
        "title": "Quiet Clearing",
        "desc": (
            "You step into a small clearing. Birds chirp softly. A stone marker stands in the center, "
            "pointing down two paths: one leads deeper into the woods, the other toward running water."
        ),
        "choices": {
            "path_woods": {
                "desc": "Follow the path into the woods.",
                "result_scene": "forest_path",
            },
            "path_water": {
                "desc": "Walk toward the sound of water.",
                "result_scene": "riverbank",
            },
        },
    },

    "forest_path": {
        "title": "Forest Path",
        "desc": (
            "The forest grows taller and darker, but peaceful. The blue glow you saw earlier is brighter "
            "now, like a beacon calling you forward. You hear a river flowing nearby."
        ),
        "choices": {
            "approach_glow": {
                "desc": "Move toward the glowing light.",
                "result_scene": "beacon_tree",
            },
            "go_to_river": {
                "desc": "Head toward the river.",
                "result_scene": "riverbank",
            },
        },
    },

    "riverbank": {
        "title": "Riverbank",
        "desc": (
            "A calm river flows gently. A narrow wooden bridge crosses to the opposite side, where the blue "
            "glow is even stronger. A wooden sign reads: 'Beacon Tree Ahead.'"
        ),
        "choices": {
            "cross_bridge": {
                "desc": "Cross the bridge.",
                "result_scene": "beacon_tree",
            },
            "fill_flask": {
                "desc": "Fill your water flask at the river.",
                "result_scene": "forest_path",
                "effects": {"add_journal": "You collected fresh river water."},
            },
        },
    },

    "beacon_tree": {
        "title": "Beacon Tree",
        "desc": (
            "You stand before the Beacon Tree — an enormous ancient tree with glowing blue runes carved into "
            "its bark. A stone pedestal nearby has a shallow slot shaped like either a charm or a map."
        ),
        "choices": {
            "place_charm": {
                "desc": "Place the wooden charm into the pedestal.",
                "result_scene": "beacon_activated",
                "effects": {"add_journal": "You activated the Beacon Tree with the charm."},
            },
            "place_map": {
                "desc": "Lay the paper map onto the pedestal.",
                "result_scene": "beacon_activated",
                "effects": {"add_journal": "You activated the Beacon Tree with the map."},
            },
        },
    },

    "beacon_activated": {
        "title": "Beacon Activated",
        "desc": (
            "A warm, bright pulse of blue light flows through the forest. The Beacon Tree awakens, humming "
            "softly with ancient magic. You feel peace wash over you. Your journey is complete."
        ),
        "choices": {
            "restart": {
                "desc": "Walk back to the forest edge to begin again.",
                "result_scene": "intro",
            },
        },
    },
}

# -------------------------
# Userdata
# -------------------------
@dataclass
class Userdata:
    player_name: Optional[str] = None
    current_scene: str = "intro"
    history: List[Dict] = field(default_factory=list)
    journal: List[str] = field(default_factory=list)
    inventory: List[str] = field(default_factory=list)
    named_npcs: Dict[str, str] = field(default_factory=lambda: {"Aeris": "Forest Guide"})
    choices_made: List[str] = field(default_factory=list)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

# -------------------------
# Helpers
# -------------------------
def scene_text(scene_key: str, userdata: Userdata) -> str:
    scene = WORLD.get(scene_key)
    if not scene:
        return "You stand in an unknown place. What do you do?"

    desc = f"{scene['desc']}\n\nChoices:\n"
    for cid, cmeta in scene["choices"].items():
        desc += f"- {cmeta['desc']} (say: {cid})\n"
    return desc + "\nWhat do you do?"

def apply_effects(effects: dict, userdata: Userdata):
    if not effects:
        return
    if "add_journal" in effects:
        userdata.journal.append(effects["add_journal"])
    if "add_inventory" in effects:
        userdata.inventory.append(effects["add_inventory"])

def summarize_scene_transition(old_scene, action_key, new_scene, userdata):
    userdata.history.append({
        "from": old_scene,
        "action": action_key,
        "to": new_scene,
        "time": datetime.utcnow().isoformat() + "Z",
    })
    userdata.choices_made.append(action_key)
    return f"You chose '{action_key}'."

# -------------------------
# Tools
# -------------------------
@function_tool
async def start_adventure(ctx: RunContext[Userdata], player_name: Annotated[Optional[str], Field(description="Player name")] = None):
    userdata = ctx.userdata
    if player_name:
        userdata.player_name = player_name

    userdata.current_scene = "intro"
    userdata.history.clear()
    userdata.journal.clear()
    userdata.inventory.clear()
    userdata.named_npcs = {"Aeris": "Forest Guide"}
    userdata.session_id = str(uuid.uuid4())[:8]
    userdata.started_at = datetime.utcnow().isoformat() + "Z"

    opening = (
        f"Aeris to {userdata.player_name or 'traveler'}. Welcome to the Forest Edge.\n\n"
        + scene_text("intro", userdata)
    )
    return opening

@function_tool
async def get_scene(ctx: RunContext[Userdata]):
    userdata = ctx.userdata
    return scene_text(userdata.current_scene, userdata)

@function_tool
async def player_action(ctx: RunContext[Userdata], action: Annotated[str, Field(description="Player action")] ):
    userdata = ctx.userdata
    scene = WORLD.get(userdata.current_scene)
    action_text = action.lower().strip()

    # Direct key match
    chosen = None
    if action_text in scene["choices"]:
        chosen = action_text

    # Fuzzy match
    if not chosen:
        for cid, meta in scene["choices"].items():
            if cid in action_text:
                chosen = cid
                break
            if any(word in action_text for word in meta["desc"].lower().split()[:3]):
                chosen = cid
                break

    if not chosen:
        return (
            "//Aeris// I'm sorry, traveler… I didn't understand that.\n\n"
            + scene_text(userdata.current_scene, userdata)
        )

    choice = scene["choices"][chosen]
    result_scene = choice["result_scene"]
    apply_effects(choice.get("effects"), userdata)

    note = summarize_scene_transition(userdata.current_scene, chosen, result_scene, userdata)
    userdata.current_scene = result_scene

    reply = (
        f"//Aeris// Very well.\n\n{note}\n\n"
        + scene_text(result_scene, userdata)
    )
    return reply

@function_tool
async def show_journal(ctx: RunContext[Userdata]):
    userdata = ctx.userdata
    out = [f"Journey ID: {userdata.session_id}"]

    if userdata.player_name:
        out.append(f"Traveler: {userdata.player_name}")

    out.append("\nJournal Notes:")
    out.extend(f"- {j}" for j in userdata.journal) if userdata.journal else out.append("None yet.")

    out.append("\nInventory:")
    out.extend(f"- {i}" for i in userdata.inventory) if userdata.inventory else out.append("Empty.")

    out.append("\nRecent Steps:")
    for h in userdata.history[-6:]:
        out.append(f"- {h['from']} -> {h['to']} via {h['action']}")

    out.append("\nWhat do you do?")
    return "\n".join(out)

@function_tool
async def restart_adventure(ctx: RunContext[Userdata]):
    userdata = ctx.userdata
    userdata.current_scene = "intro"
    userdata.history.clear()
    userdata.journal.clear()
    userdata.inventory.clear()
    userdata.choices_made.clear()
    userdata.session_id = str(uuid.uuid4())[:8]

    greeting = (
        "//Aeris// The forest breathes anew. Your journey begins once more.\n\n"
        + scene_text("intro", userdata)
    )
    return greeting

# -------------------------
# Agent
# -------------------------
class ForestBeaconAgent(Agent):
    def __init__(self):
        instructions = """
        You are Aeris, the gentle forest guide and Game Master of the Forest Beacon Adventure.
        Universe: A peaceful, enchanted forest filled with soft light, glowing trees, and calm magic.
        Tone: Soft, kind, supportive, and poetic.
        Role: You describe scenes gently and guide the traveler. Every response must end with:
              "What do you do?"
        Rules:
            - Use the provided tools.
            - Maintain continuity using userdata.
            - Never break persona.
        """
        super().__init__(instructions=instructions, tools=[start_adventure, get_scene, player_action, show_journal, restart_adventure])

# -------------------------
# Entrypoint & Prewarm
# -------------------------
def prewarm(proc: JobProcess):
    try:
        proc.userdata["vad"] = silero.VAD.load()
    except Exception:
        logger.warning("VAD prewarm failed.")

async def entrypoint(ctx: JobContext):
    logger.info("🌲 Starting Forest Beacon Agent")

    userdata = Userdata()
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(voice="en-US-marcus", style="Conversational", text_pacing=True),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata.get("vad"),
        userdata=userdata,
    )

    await session.start(
        agent=ForestBeaconAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC())
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm
        )
    )
