from __future__ import annotations
import asyncio, json, os, uuid
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .pipeline import run_file

# SQLite by default; set DATABASE_URL=postgresql+psycopg://... for PostgreSQL.
engine = create_engine(os.environ.get("DATABASE_URL", "sqlite:///./medlegal.db"),
                       connect_args={"check_same_thread": False} if "sqlite" in os.environ.get("DATABASE_URL", "sqlite") else {})
Base = declarative_base()
Session = sessionmaker(bind=engine)


class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True)
    path = Column(String); status = Column(String, default="queued")
    result = Column(Text, nullable=True)


Base.metadata.create_all(engine)
app = FastAPI(title="medlegal-extract")


class Submit(BaseModel):
    path: str
    provider: str = "stub"


def _run(job_id: str, path: str, provider: str):
    with Session() as s:
        job = s.get(Job, job_id); job.status = "running"; s.commit()
    try:
        result = run_file(path, provider).model_dump_json()
        status = "done"
    except Exception as e:  # keep the queue alive on a bad document
        result, status = json.dumps({"error": str(e)}), "failed"
    with Session() as s:
        job = s.get(Job, job_id); job.status, job.result = status, result; s.commit()


@app.post("/jobs")
async def submit(body: Submit, bg: BackgroundTasks):
    job_id = uuid.uuid4().hex[:12]
    with Session() as s:
        s.add(Job(id=job_id, path=body.path)); s.commit()
    bg.add_task(_run, job_id, body.path, body.provider)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
async def status(job_id: str):
    with Session() as s:
        job = s.get(Job, job_id)
        if not job: raise HTTPException(404, "job not found")
        return {"job_id": job.id, "status": job.status}


@app.get("/jobs/{job_id}/result")
async def result(job_id: str):
    with Session() as s:
        job = s.get(Job, job_id)
        if not job: raise HTTPException(404, "job not found")
        if job.status != "done": return {"job_id": job.id, "status": job.status}
        return json.loads(job.result)
