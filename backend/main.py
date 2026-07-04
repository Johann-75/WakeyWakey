import asyncio
from contextlib import asynccontextmanager
import os
from time import perf_counter

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine, get_db
from models import Check, Url
from schemas import CheckResponse, HealthResponse, UrlCreate, UrlResponse, UrlWithLatestCheck


CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))
MAX_CONCURRENT_CHECKS = int(os.getenv("MAX_CONCURRENT_CHECKS", "20"))
scheduler = AsyncIOScheduler()


async def fetch_url_status(
    client: httpx.AsyncClient,
    url_id: int,
    url: str,
    semaphore: asyncio.Semaphore,
) -> Check:
    status_code = None
    response_time_ms = None
    is_up = False
    async with semaphore:
        started_at = perf_counter()
        try:
            response = await client.get(url)
            response_time_ms = round((perf_counter() - started_at) * 1000, 2)
            status_code = response.status_code
            is_up = 200 <= response.status_code < 400
        except Exception:
            # Connection failure, timeout, DNS failure, ssl/value errors, etc.
            response_time_ms = None
            status_code = None
            is_up = False

    return Check(
        url_id=url_id,
        status_code=status_code,
        response_time_ms=response_time_ms,
        is_up=is_up,
    )


async def check_single_url_task(url_id: int, url: str) -> None:
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as client:
            sem = asyncio.Semaphore(1)
            check = await fetch_url_status(client, url_id, url, sem)
        db = SessionLocal()
        try:
            db.add(check)
            db.commit()
        except IntegrityError:
            db.rollback()
        finally:
            db.close()
    except Exception:
        pass


async def check_all_urls_async() -> None:
    db = SessionLocal()
    try:
        urls = [(url.id, url.url) for url in db.scalars(select(Url)).all()]
    finally:
        db.close()

    if not urls:
        return

    sem = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=REQUEST_TIMEOUT_SECONDS,
    ) as client:
        checks = await asyncio.gather(
            *(fetch_url_status(client, url_id, url, sem) for url_id, url in urls)
        )

    db = SessionLocal()
    try:
        db.add_all(checks)
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    scheduler.add_job(
        check_all_urls_async,
        "interval",
        seconds=CHECK_INTERVAL_SECONDS,
        id="check_all_urls",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="URL Uptime Monitor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/urls", response_model=UrlResponse, status_code=status.HTTP_201_CREATED)
async def create_url(
    payload: UrlCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Url:
    url = Url(url=str(payload.url))
    db.add(url)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="URL already exists",
        ) from exc

    db.refresh(url)
    background_tasks.add_task(check_single_url_task, url.id, url.url)
    return url


@app.get("/urls", response_model=list[UrlWithLatestCheck])
def list_urls(db: Session = Depends(get_db)) -> list[UrlWithLatestCheck]:
    urls = db.scalars(select(Url).order_by(Url.created_at.desc())).all()
    if not urls:
        return []

    url_ids = [url.id for url in urls]

    # Fetch last 10 checks per URL in one query using ROW_NUMBER() CTE
    subq = (
        select(
            Check,
            func.row_number().over(
                partition_by=Check.url_id,
                order_by=(Check.checked_at.desc(), Check.id.desc())
            ).label("rn")
        )
        .where(Check.url_id.in_(url_ids))
        .cte("ranked_checks")
    )

    stmt = (
        select(Check)
        .join(subq, Check.id == subq.c.id)
        .where(subq.c.rn <= 10)
        .order_by(Check.url_id, Check.checked_at.desc(), Check.id.desc())
    )
    checks = db.scalars(stmt).all()

    from collections import defaultdict
    checks_by_url = defaultdict(list)
    for check in checks:
        checks_by_url[check.url_id].append(check)

    response = []
    for url in urls:
        recent_checks = checks_by_url[url.id]
        latest_check = recent_checks[0] if recent_checks else None
        
        response.append(
            UrlWithLatestCheck(
                id=url.id,
                url=url.url,
                created_at=url.created_at,
                status_code=latest_check.status_code if latest_check else None,
                response_time_ms=latest_check.response_time_ms if latest_check else None,
                is_up=latest_check.is_up if latest_check else None,
                checked_at=latest_check.checked_at if latest_check else None,
                recent_checks=recent_checks,
            )
        )

    return response


@app.get("/urls/{url_id}/checks", response_model=list[CheckResponse])
def list_checks(url_id: int, db: Session = Depends(get_db)) -> list[Check]:
    url = db.get(Url, url_id)
    if not url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL not found")

    return db.scalars(
        select(Check)
        .where(Check.url_id == url_id)
        .order_by(Check.checked_at.desc(), Check.id.desc())
    ).all()


@app.delete("/urls/{url_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_url(url_id: int, db: Session = Depends(get_db)) -> None:
    url = db.get(Url, url_id)
    if not url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL not found")

    db.delete(url)
    db.commit()
