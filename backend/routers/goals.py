from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from memory import goals

router = APIRouter()


class GoalCreate(BaseModel):
    title:       str
    description: str = ""
    category:    str = "personal"
    priority:    int = 3
    deadline:    Optional[str] = None
    milestones:  list[str] = []


class GoalUpdate(BaseModel):
    title:       Optional[str] = None
    description: Optional[str] = None
    status:      Optional[str] = None
    priority:    Optional[int] = None
    deadline:    Optional[str] = None


class ProgressNote(BaseModel):
    note: str


class MilestoneComplete(BaseModel):
    milestone_text: str


@router.get("")
def list_goals():
    return {"goals": goals.get_all()}


@router.get("/active")
def active_goals():
    return {"goals": goals.get_active()}


@router.get("/alerts")
def deadline_alerts():
    return {"alerts": goals.get_deadline_alerts()}


@router.post("")
def create_goal(req: GoalCreate):
    gid = goals.add_goal(
        title=req.title, description=req.description,
        category=req.category, priority=req.priority,
        deadline=req.deadline, milestones=req.milestones,
    )
    return {"id": gid, "message": "Goal created"}


@router.patch("/{goal_id}")
def update_goal(goal_id: str, req: GoalUpdate):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    goals.update_goal(goal_id, **updates)
    return {"message": "Updated"}


@router.post("/{goal_id}/progress")
def add_progress(goal_id: str, req: ProgressNote):
    goals.add_progress_note(goal_id, req.note)
    return {"message": "Progress noted"}


@router.post("/{goal_id}/milestone")
def complete_milestone(goal_id: str, req: MilestoneComplete):
    goals.complete_milestone(goal_id, req.milestone_text)
    return {"message": "Milestone completed"}


@router.delete("/{goal_id}")
def delete_goal(goal_id: str):
    goals.delete_goal(goal_id)
    return {"message": "Deleted"}
