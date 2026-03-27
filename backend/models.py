from pydantic import BaseModel, Field
from typing import List, Optional

# --- ADMIN ENDPOINTS ---

class TeamCreateRequest(BaseModel):
    team_id: str = Field(..., min_length=1, description="Unique alphanumeric team identifier")

class TeamCreateResponse(BaseModel):
    status: str
    team_id: str

class ProblemAssignRequest(BaseModel):
    team_id: str = Field(..., min_length=1, description="Team ID to assign problems to")
    problem_ids: List[str] = Field(..., min_length=2, max_length=2, description="Exactly 2 problem IDs per team")

class StandardResponse(BaseModel):
    status: str
    message: Optional[str] = None

# --- PLAYER ENDPOINTS ---

class JoinRequest(BaseModel):
    team_id: str = Field(..., min_length=1, description="Team ID to join")
    name: str = Field(..., min_length=1, description="Player alias/name")

class JoinResponse(BaseModel):
    status: str
    session_token: str
    team_id: str
    player_id: int

class ProblemSummary(BaseModel):
    id: str
    title: str
    description: str

class ProblemDetail(ProblemSummary):
    part_a_prompt: str
    part_b_prompt: str
    interface_stub: str
    language: str

class TeamProblemsResponse(BaseModel):
    team_id: str
    problems: List[ProblemSummary]
