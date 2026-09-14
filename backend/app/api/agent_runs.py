from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import AgentRun
from app.domain.models import AgentRunOut

router = APIRouter(prefix="/api/agent-runs", tags=["agent-runs"])


@router.get("", response_model=list[AgentRunOut])
def list_agent_runs(db: Session = Depends(get_db)):
    return db.query(AgentRun).order_by(AgentRun.id.desc()).all()


@router.get("/{run_id}", response_model=AgentRunOut)
def get_agent_run(run_id: int, db: Session = Depends(get_db)):
    row = db.get(AgentRun, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No agent run with id={run_id}")
    return row
