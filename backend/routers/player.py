from fastapi import APIRouter, Depends, HTTPException
import aiosqlite
import uuid
from ..database import get_db
from ..models import JoinRequest, JoinResponse, TeamProblemsResponse, ProblemSummary, ProblemDetail
from ..problems.problem_loader import get_problem

router = APIRouter(tags=["player"])

@router.post("/join", response_model=JoinResponse)
async def join_team(request: JoinRequest, db: aiosqlite.Connection = Depends(get_db)):
    # Validate team exists
    async with db.execute("SELECT team_id FROM teams WHERE team_id = ?", (request.team_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Team not found")

    # Enforce max 2 players per team
    async with db.execute("SELECT COUNT(*) FROM players WHERE team_id = ?", (request.team_id,)) as cursor:
        row = await cursor.fetchone()
        if row and row[0] >= 2:
            raise HTTPException(status_code=400, detail="Team is already full (2 players max)")

    session_token = str(uuid.uuid4())

    await db.execute(
        "INSERT INTO players (team_id, name, session_token) VALUES (?, ?, ?)",
        (request.team_id, request.name, session_token)
    )
    await db.commit()

    # Retrieve the auto-generated player ID
    async with db.execute("SELECT id FROM players WHERE session_token = ?", (session_token,)) as cursor:
        player_row = await cursor.fetchone()
        player_id = player_row[0]

    return JoinResponse(
        status="success",
        session_token=session_token,
        team_id=request.team_id,
        player_id=player_id
    )

@router.get("/team/{team_id}/problems", response_model=TeamProblemsResponse)
async def get_team_problems(team_id: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT problem_id FROM team_problems WHERE team_id = ?", (team_id,)) as cursor:
        rows = await cursor.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No problems assigned to this team")

    problems = []
    for row in rows:
        p_id = row[0]
        p_detail = get_problem(p_id)
        if p_detail:
            problems.append(ProblemSummary(
                id=p_detail.id,
                title=p_detail.title,
                description=p_detail.description
            ))

    return TeamProblemsResponse(team_id=team_id, problems=problems)

@router.get("/problem/{problem_id}", response_model=ProblemDetail)
async def get_problem_details(problem_id: str):
    problem = get_problem(problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return problem
