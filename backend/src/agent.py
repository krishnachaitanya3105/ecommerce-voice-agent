import logging
import json
import os
import asyncio
from datetime import datetime
from typing import Annotated, Optional
from dataclasses import dataclass, asdict

print("\n" + "💼" * 50)
print("🚀 AI SDR AGENT (PROJECT MANAGEMENT — ZOHO PROJECTS)")
print("💡 SDR_Agent.py LOADED SUCCESSFULLY!")
print("💼" * 50 + "\n")

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

# Plugins
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")


# ======================================================
# 📌 1. DATA PATHS (store data folder outside src/)
# ======================================================
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BACKEND_DIR, "zoho_projects_data")
FAQ_FILE = "zoho_projects_faq.json"
LEADS_FILE = "zoho_projects_leads.json"

# ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

FAQ_PATH = os.path.join(DATA_DIR, FAQ_FILE)
LEADS_PATH = os.path.join(DATA_DIR, LEADS_FILE)


# ======================================================
# 📌 2. DEFAULT FAQ CONTENT + FEATURE DETAILS
# ======================================================

DEFAULT_FAQ = [
    {
        "question": "What is Zoho Projects?",
        "answer": (
            "Zoho Projects is a cloud-based project management tool that helps teams plan tasks, "
            "track progress, collaborate, and manage workflows efficiently."
        ),
    },
    {
        "question": "Who is Zoho Projects for?",
        "answer": (
            "Zoho Projects is ideal for teams in software development, marketing, agencies, operations, "
            "and any team that needs to plan and track projects with deadlines."
        ),
    },
    {
        "question": "Do you have a free plan?",
        "answer": (
            "Yes. Zoho Projects offers a free plan with limited projects and users, suitable for small teams "
            "who are just getting started."
        ),
    },
    {
        "question": "What is your pricing?",
        "answer": (
            "Zoho Projects has paid plans such as Premium and Enterprise with per-user monthly pricing. "
            "Pricing varies based on features and billing cycle, and can be viewed on the Zoho Projects pricing page."
        ),
    },
    {
        "question": "Do you offer a free trial?",
        "answer": "Yes. Zoho Projects offers a free trial period on its paid plans so you can try all features before upgrading.",
    },
    {
        "question": "Do you offer mobile apps?",
        "answer": "Yes. Zoho Projects has mobile apps for iOS and Android so you can manage tasks on the go.",
    },
    {
        "question": "Do you support integrations?",
        "answer": (
            "Yes. Zoho Projects integrates with Zoho apps and third-party tools like Google Workspace, "
            "Microsoft Office 365, Slack, GitHub, and more."
        ),
    },
    {
        "question": "Do you offer time tracking?",
        "answer": (
            "Yes. Zoho Projects includes built-in time tracking with timesheets, billable hours, and time reports."
        ),
    },
]

# Detailed feature descriptions (used by the new tool)
FEATURES = {
    "task management": {
        "title": "Task Management",
        "summary": (
            "Create tasks, assign owners, set priorities and deadlines, and organize work into task lists. "
            "You can add checklists, attachments, comments, and track status from start to completion."
        ),
        "highlights": [
            "Create and assign tasks to team members",
            "Set priorities, due dates, and reminders",
            "Use subtasks and checklists for detailed workflows",
            "Add comments, files, and links for context",
        ],
    },
    "gantt charts": {
        "title": "Gantt Charts",
        "summary": (
            "Visualize project timelines, dependencies, and milestones with interactive Gantt charts. "
            "Easily drag and adjust tasks as plans change."
        ),
        "highlights": [
            "View project schedule along a timeline",
            "Set task dependencies and adjust them visually",
            "Track milestones and critical paths",
            "Compare planned vs actual timelines in higher plans",
        ],
    },
    "time tracking": {
        "title": "Time Tracking & Timesheets",
        "summary": (
            "Track how much time is spent on each task or project using timesheets and timers, "
            "and generate reports for billing or productivity analysis."
        ),
        "highlights": [
            "Start timers directly on tasks",
            "Log hours manually into timesheets",
            "Separate billable and non-billable hours",
            "Export time data for clients or payroll",
        ],
    },
    "collaboration": {
        "title": "Team Collaboration",
        "summary": (
            "Keep all project communication in one place with comments, feeds, chat, forums, and file sharing."
        ),
        "highlights": [
            "Comment directly on tasks and issues",
            "Use project feeds to see recent updates",
            "Create project forums for discussions",
            "Upload and share files with version history",
        ],
    },
    "automation": {
        "title": "Automation & Blueprints",
        "summary": (
            "Automate repetitive steps in your workflows using Blueprints, custom rules, and notifications."
        ),
        "highlights": [
            "Define step-by-step workflows for tasks",
            "Trigger actions when tasks move between stages",
            "Send automated reminders and notifications",
            "Reduce manual work and enforce processes",
        ],
    },
    "integrations": {
        "title": "Integrations",
        "summary": (
            "Connect Zoho Projects with other tools you already use, including Zoho apps and third-party services."
        ),
        "highlights": [
            "Integrate with Zoho CRM, Zoho Books, Zoho Sprints, and more",
            "Connect with Google Workspace and Microsoft Office 365",
            "Use Slack, GitHub, Bitbucket integrations",
            "Automate workflows further using integration platforms",
        ],
    },
    "reports": {
        "title": "Reports & Dashboards",
        "summary": (
            "Get visibility into project progress, resource utilization, and time spent with built-in reports and dashboards."
        ),
        "highlights": [
            "Track project status with visual dashboards",
            "View workload and utilization reports",
            "Analyze timesheet data and task metrics",
            "Export reports for stakeholders or clients",
        ],
    },
    "mobile apps": {
        "title": "Mobile Apps",
        "summary": (
            "Manage projects from anywhere with Zoho Projects mobile apps on iOS and Android."
        ),
        "highlights": [
            "Create and update tasks on the go",
            "Track time from your phone",
            "Get push notifications for important updates",
            "Collaborate with your team remotely",
        ],
    },
}


def load_faq():
    """Create FAQ file if missing, then load it."""
    try:
        if not os.path.exists(FAQ_PATH):
            with open(FAQ_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_FAQ, f, indent=4)

        with open(FAQ_PATH, "r", encoding="utf-8") as f:
            return json.dumps(json.load(f))
    except Exception as e:
        print("⚠️ FAQ Load Error:", e)
        return ""


STORE_FAQ_TEXT = load_faq()


# ======================================================
# 📌 3. LEAD DATA STRUCTURE
# ======================================================

@dataclass
class LeadProfile:
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    use_case: Optional[str] = None
    team_size: Optional[str] = None
    timeline: Optional[str] = None

    def is_qualified(self):
        # Simple qualification rule: at least name, email, and use case
        return all([self.name, self.email, self.use_case])


@dataclass
class Userdata:
    lead_profile: LeadProfile


# ======================================================
# 📌 4. LEAD CAPTURE TOOLS
# ======================================================

@function_tool
async def update_lead_profile(
    ctx: RunContext[Userdata],
    name: Annotated[Optional[str], Field(description="Customer name")] = None,
    company: Annotated[Optional[str], Field(description="Company name")] = None,
    email: Annotated[Optional[str], Field(description="Email address")] = None,
    role: Annotated[Optional[str], Field(description="Job role")] = None,
    use_case: Annotated[Optional[str], Field(description="User goal / use case for Zoho Projects")] = None,
    team_size: Annotated[Optional[str], Field(description="Team size using Zoho Projects")] = None,
    timeline: Annotated[Optional[str], Field(description="Timeline to start (now / soon / later)")] = None,
) -> str:

    profile = ctx.userdata.lead_profile

    # Update only the fields provided
    if name:
        profile.name = name.strip()
    if company:
        profile.company = company.strip()
    if email:
        profile.email = email.strip()
    if role:
        profile.role = role.strip()
    if use_case:
        profile.use_case = use_case.strip()
    if team_size:
        profile.team_size = team_size.strip()
    if timeline:
        profile.timeline = timeline.strip()

    print("📝 LEAD UPDATED:", profile)
    # Helpful return so the agent can speak a confirmation
    confirmations = []
    if name:
        confirmations.append(f"name = {profile.name}")
    if email:
        confirmations.append(f"email = {profile.email}")
    if role:
        confirmations.append(f"role = {profile.role}")
    if company and profile.company:
        confirmations.append(f"company = {profile.company}")
    if use_case:
        confirmations.append(f"use_case = {profile.use_case}")
    if team_size:
        confirmations.append(f"team_size = {profile.team_size}")
    if timeline:
        confirmations.append(f"timeline = {profile.timeline}")

    if confirmations:
        return "Got it — " + ", ".join(confirmations) + "."
    else:
        return "Got it. Thanks!"


@function_tool
async def submit_lead_and_end(ctx: RunContext[Userdata]) -> str:
    """Save to JSON file (no extra dependencies)."""

    profile = ctx.userdata.lead_profile

    entry = asdict(profile)
    entry["timestamp"] = datetime.now().isoformat()

    # Ensure directory exists
    os.makedirs(os.path.dirname(LEADS_PATH), exist_ok=True)

    leads = []
    if os.path.exists(LEADS_PATH):
        try:
            with open(LEADS_PATH, "r", encoding="utf-8") as f:
                leads = json.load(f)
        except Exception as e:
            print("⚠️ Error loading existing leads:", e)
            leads = []

    # If company is missing we just keep it as None or empty; no special handling needed
    if not entry.get("company"):
        entry["company"] = entry.get("company")  # keep None or empty

    # Append and save
    leads.append(entry)

    try:
        with open(LEADS_PATH, "w", encoding="utf-8") as f:
            json.dump(leads, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print("⚠️ Error saving lead file:", e)
        return "Sorry, there was an error saving your details. Please try again."

    print(f"✅ LEAD SAVED → {LEADS_PATH}")

    # Friendly spoken confirmation
    friendly_name = profile.name if profile.name else "there"
    email_note = f" We'll email more details to {profile.email}." if profile.email else ""
    return (
        f"Thanks {friendly_name}! Your details have been saved.{email_note} Have a great day!"
    )


# ======================================================
# 📌 4b. FEATURE DETAILS TOOL
# ======================================================

@function_tool
async def get_feature_details(
    ctx: RunContext[Userdata],
    feature_name: Annotated[str, Field(description="Feature name to fetch details for, e.g., 'Task Management', 'Gantt Charts', 'Time Tracking'")],
) -> str:
    """Return a summary and highlights for a requested feature if available."""
    key = feature_name.strip().lower()

    # Try exact key match first
    if key in FEATURES:
        f = FEATURES[key]
        highlights_text = "\n  - ".join(f["highlights"]) if f.get("highlights") else ""
        return (
            f"{f['title']}.\n"
            f"Summary: {f.get('summary')}\n"
            f"Key points:\n  - {highlights_text}"
        )

    # Fuzzy match based on title containing the query
    for k, f in FEATURES.items():
        if feature_name.strip().lower() in f["title"].lower():
            highlights_text = "\n  - ".join(f["highlights"]) if f.get("highlights") else ""
            return (
                f"{f['title']}.\n"
                f"Summary: {f.get('summary')}\n"
                f"Key points:\n  - {highlights_text}"
            )

    # not found
    return (
        "Sorry — I couldn't find details for that feature. "
        "You can ask about: Task Management, Gantt Charts, Time Tracking, Collaboration, Automation, Integrations, Reports, or Mobile Apps."
    )


# ======================================================
# 📌 5. SDR AGENT (Maya)
# ======================================================

class SDRAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=f"""
You are **Maya**, a friendly Sales Development Representative (SDR) for **Zoho Projects**, a project management SaaS.

💬 Your Job:
- Greet visitors warmly as they join.
- Ask what brought them here and what kind of projects or workflows they are managing.
- Answer questions about Zoho Projects using the FAQ below and the feature details tool.
- Keep answers short, clear, and tied to project management use cases.
- Never invent pricing or features beyond what is in the FAQ or feature descriptions.

Lead capture:
- Naturally ask for:
  - Name
  - Company
  - Email
  - Role
  - Use case (what they want to use Zoho Projects for)
  - Team size
  - Timeline (now / soon / later)
- Whenever the user shares any of these details, call the `update_lead_profile` tool with the relevant fields.
- Do NOT read the JSON structure aloud; just confirm in natural language.

Call tools:
- When the user shares their details (name, email, company, role, use case, team size, timeline), call `update_lead_profile`.
- When the user asks about a specific feature (e.g. "Tell me about Gantt charts", "How does time tracking work?", "What about task management?"),
  call `get_feature_details` with the feature name and then read the tool's response in a friendly way.
- When the user indicates they are done (e.g. says "that's all", "I'm done", "no more questions", "bye", "thank you"), call `submit_lead_and_end`.

End-of-call:
- After `submit_lead_and_end` responds, briefly summarize who they are and what they are looking for, based on the lead profile you have,
  and politely close the conversation.

📘 FAQ DATA (use this as your ground truth):
{STORE_FAQ_TEXT}

Behavior & rules:
- Be conversational, warm, and professional.
- Ask one question at a time.
- Do not overwhelm the user with too many questions in one turn.
- If information is missing, gently follow up, but do not be pushy.
- If you don't find something in the FAQ or features, say you are not sure and suggest visiting the Zoho Projects website for more details.
""",
            tools=[update_lead_profile, submit_lead_and_end, get_feature_details],
        )


# ======================================================
# 📌 6. ENTRYPOINT (LiveKit Worker)
# ======================================================

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):

    ctx.log_context_fields = {"room": ctx.room.name}
    print("\n🔵 Zoho Projects SDR Agent starting...\n")

    userdata = Userdata(lead_profile=LeadProfile())

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(voice="en-US-natalie", style="Promo", text_pacing=True),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        userdata=userdata,
    )

    await session.start(
        agent=SDRAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )

    await ctx.connect()


# ======================================================
# 📌 7. RUN FILE
# ======================================================

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm
        )
    )
