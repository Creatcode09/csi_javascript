from fastapi import APIRouter, Depends, HTTPException
import aiosqlite
from ..database import get_db
from ..models import TeamCreateRequest, TeamCreateResponse, ProblemAssignRequest, StandardResponse
from ..problems.problem_loader import get_problem

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/create-team", response_model=TeamCreateResponse)
async def create_team(request: TeamCreateRequest, db: aiosqlite.Connection = Depends(get_db)):
    # Check if team already exists
    async with db.execute("SELECT team_id FROM teams WHERE team_id = ?", (request.team_id,)) as cursor:
        if await cursor.fetchone():
            raise HTTPException(status_code=400, detail="Team ID already exists")

    await db.execute("INSERT INTO teams (team_id) VALUES (?)", (request.team_id,))
    await db.commit()
    return TeamCreateResponse(status="success", team_id=request.team_id)

@router.post("/assign-problems", response_model=StandardResponse)
async def assign_problems(request: ProblemAssignRequest, db: aiosqlite.Connection = Depends(get_db)):
    # Pydantic already enforces exactly 2 via min_length/max_length on problem_ids
    if len(set(request.problem_ids)) != 2:
        raise HTTPException(status_code=400, detail="Problem IDs must be unique within the assignment")

    # Validate each problem exists in the cache
    for p_id in request.problem_ids:
        if get_problem(p_id) is None:
            raise HTTPException(status_code=400, detail=f"Problem '{p_id}' not found in loaded problems")

    # Validate team exists
    async with db.execute("SELECT team_id FROM teams WHERE team_id = ?", (request.team_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Team not found")

    # Check if problems are already assigned to this team
    async with db.execute("SELECT COUNT(*) FROM team_problems WHERE team_id = ?", (request.team_id,)) as cursor:
        row = await cursor.fetchone()
        if row and row[0] > 0:
            raise HTTPException(status_code=400, detail="Problems already assigned to this team")

    # Insert the 2 problem assignments
    for p_id in request.problem_ids:
        await db.execute("INSERT INTO team_problems (team_id, problem_id) VALUES (?, ?)", (request.team_id, p_id))
    await db.commit()
    return StandardResponse(status="success", message="Problems assigned successfully")
