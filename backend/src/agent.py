"""
DSA Tutor Agent – Day 4 Teach-the-Tutor
Company: CodeSense Academy

This single-file agent follows the Day-4 Teach-the-Tutor pattern:
- Small JSON knowledge base (auto-created)
- Three modes: learn (Matthew), quiz (Alicia), teach_back (Ken)
- User can switch mode anytime
- Evaluates user explanation using keyword overlap scoring
- Uses Murf Falcon + LiveKit Agents

Run: python dsa_tutor_agent.py
"""

import logging
import json
import os
from dataclasses import dataclass
from typing import Literal, Optional, Annotated

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

# Voice + STT Plugins
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("dsa_tutor_agent")
load_dotenv(".env.local")

# -----------------------------
# Company Name
# -----------------------------
COMPANY_NAME = "CodeSense Academy"

# -----------------------------
# Content JSON
# -----------------------------
DATA_DIR = "shared-data"
CONTENT_FILE = os.path.join(DATA_DIR, "dsa_tutor_content.json")

DEFAULT_CONTENT = [
    {
        "id": "variables",
        "title": "Variables",
        "summary": "Variables store values in memory so programs can access and modify them. Each variable has a name, a type, and a value. They help reuse values multiple times without rewriting them.",
        "sample_question": "What is a variable and why is it important in programming?"
    },
    {
        "id": "loops",
        "title": "Loops",
        "summary": "Loops allow repeating a block of code multiple times. 'For' loops run when the number of iterations is known, while 'while' loops run until a condition changes.",
        "sample_question": "Explain the difference between a for loop and a while loop."
    },
    {
        "id": "binary_search",
        "title": "Binary Search",
        "summary": "Binary Search is an efficient way to search a sorted array by repeatedly dividing the search range in half. This reduces time complexity to O(log n).",
        "sample_question": "Why is binary search faster than linear search?"
    },
    {
        "id": "oop_basics",
        "title": "OOP Basics",
        "summary": "Object-Oriented Programming organizes code into objects and classes. Four key principles: Encapsulation, Inheritance, Polymorphism, and Abstraction.",
        "sample_question": "What are the four pillars of OOP?"
    }
]


def ensure_content_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CONTENT_FILE):
        with open(CONTENT_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONTENT, f, indent=2)
        print(f"Created DSA content at {CONTENT_FILE}")


def load_content():
    ensure_content_file()
    with open(CONTENT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


COURSE_CONTENT = load_content()

# -----------------------------
# State
# -----------------------------
@dataclass
class TutorState:
    current_topic_id: Optional[str] = None
    current_topic_data: Optional[dict] = None
    mode: Literal["learn", "quiz", "teach_back"] = "learn"

    def set_topic(self, topic_id: str) -> bool:
        topic_id = topic_id.lower()
        topic = next((t for t in COURSE_CONTENT if t["id"] == topic_id), None)
        if topic:
            self.current_topic_id = topic_id
            self.current_topic_data = topic
            return True
        return False


@dataclass
class Userdata:
    tutor_state: TutorState
    agent_session: Optional[AgentSession] = None


# -----------------------------
# Tools
# -----------------------------
@function_tool
async def select_topic(
    ctx: RunContext[Userdata],
    topic_id: Annotated[str, Field(description="Topic ID to select")]
) -> str:
    state = ctx.userdata.tutor_state
    ok = state.set_topic(topic_id)
    if ok:
        return f"Topic set to {state.current_topic_data['title']}. You can now 'learn', 'quiz', or 'teach_back'."
    avail = ", ".join([t["id"] for t in COURSE_CONTENT])
    return f"Topic not found. Available topics: {avail}"


@function_tool
async def set_learning_mode(
    ctx: RunContext[Userdata],
    mode: Annotated[str, Field(description="learn | quiz | teach_back")]
) -> str:
    state = ctx.userdata.tutor_state
    mode = mode.lower()

    if mode not in ("learn", "quiz", "teach_back"):
        return "Mode must be one of: learn, quiz, teach_back."

    state.mode = mode
    session = ctx.userdata.agent_session

    # Set correct Murf Falcon voice per mode
    if session:
        if mode == "learn":
            session.tts.update_options(voice="en-US-matthew", style="Promo")
        elif mode == "quiz":
            session.tts.update_options(voice="en-US-alicia", style="Conversational")
        else:
            session.tts.update_options(voice="en-US-ken", style="Promo")

    return f"Switched to {mode} mode."


@function_tool
async def evaluate_teaching(
    ctx: RunContext[Userdata],
    user_explanation: Annotated[str, Field(description="User's explanation for teach-back")]
) -> str:
    topic = ctx.userdata.tutor_state.current_topic_data or {}
    summary = topic.get("summary", "")
    expected_words = set(w.strip('.,?!').lower() for w in summary.split())
    answer_words = set(w.strip('.,?!').lower() for w in user_explanation.split())

    if not expected_words:
        return "No topic selected to evaluate."

    overlap = expected_words & answer_words
    score = int((len(overlap) / max(1, len(expected_words))) * 10)

    if score >= 8:
        feedback = "Excellent — you covered the key ideas well!"
    elif score >= 5:
        feedback = "Good — but you can add more details."
    elif score >= 3:
        feedback = "You explained some parts — try being more structured."
    else:
        feedback = "Try again with more details and examples."

    return f"Score: {score}/10. {feedback}"


# -----------------------------
# MAIN AGENT
# -----------------------------
class DSATutorAgent(Agent):
    def __init__(self):
        topic_list = ", ".join([f"{t['id']} ({t['title']})" for t in COURSE_CONTENT])

        super().__init__(
            instructions=f"""
You are a Computer Science Tutor for {COMPANY_NAME}.

AVAILABLE TOPICS:
{topic_list}

MODES:
  - LEARN (Matthew): Explain the concept with a simple example.
  - QUIZ (Alicia): Ask the sample_question and wait for an answer.
  - TEACH_BACK (Ken): Ask the user to explain the topic back and then evaluate.

BEHAVIOR:
  - Start by asking which topic the user wants to study.
  - Once a topic is selected, allow: learn, quiz, teach_back.
  - Use the tools select_topic, set_learning_mode, evaluate_teaching.
  - Keep responses short, friendly, and interactive.
            """,
            tools=[select_topic, set_learning_mode, evaluate_teaching],
        )


# -----------------------------
# Entrypoint
# -----------------------------
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    print(f"Starting {COMPANY_NAME} - DSA Tutor Agent")

    userdata = Userdata(tutor_state=TutorState())

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(voice="en-US-matthew", style="Promo", text_pacing=True),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        userdata=userdata,
    )

    userdata.agent_session = session

    await session.start(
        agent=DSATutorAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
