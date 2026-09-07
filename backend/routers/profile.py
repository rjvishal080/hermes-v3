from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from memory.manager import load_profile, save_profile

router = APIRouter()

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    goals: Optional[list[str]] = None
    custom_fields: Optional[dict] = None

@router.get("")
def get_profile():
    return load_profile()

@router.post("")
def update_profile(data: ProfileUpdate):
    profile = load_profile()
    if data.name is not None:          profile["name"] = data.name
    if data.bio is not None:           profile["bio"] = data.bio
    if data.goals is not None:         profile["goals"] = data.goals
    if data.custom_fields is not None: profile["custom_fields"].update(data.custom_fields)
    save_profile(profile)
    return {"message": "Profile updated", "profile": profile}

@router.put("/full")
def replace_profile(data: dict):
    save_profile(data)
    return {"message": "Profile replaced"}
