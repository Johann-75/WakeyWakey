import asyncio
from contextlib import asynccontextmanager
from time import perf_counter
from typing import NamedTuple

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine, get_db
from models import Check, Url
from schemas import CheckResponse, HealthResponse, UrlCreate, UrlResponse, UrlWithLatestCheck


CHECK_INTERVAL_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 10
scheduler = BackgroundScheduler()


class CheckResult(NamedTuple):
    url_id: int
    status_code: int | None
    response_time_ms: float | None
    is_up: bool


async def fetch_url_status(
    client: httpx.AsyncClient,
    url_id: int,
    url: str,
) -> CheckResult:
    status_code = None
    response_time_ms = None
    is_up = False
    started_at = perf_counter()

    try:
        response = await client.get(url)
        response_time_ms = round((perf_counter() - started_at) * 1000, 2)
        status_code = response.status_code
        is_up = 200 <= response.status_code < 400
    except httpx.RequestError:
        # Connection failure, timeout, DNS failure, etc.
        # No actual response was received, so response_time_ms is None
        response_time_ms = None
        status_code = None
        is_up = False

    return CheckResult(
        url_id=url_id,
        status_code=status_code,
        response_time_ms=response_time_ms,
        is_up=is_up,
    )


async def check_single_url(url_id: int, url: str) -> CheckResult:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=REQUEST_TIMEOUT_SECONDS,
    ) as client:
        return await fetch_url_status(client, url_id, url)


def insert_check(db: Session, result: CheckResult) -> Check:
    check = Check(
        url_id=result.url_id,
        status_code=result.status_code,
        response_time_ms=result.response_time_ms,
        is_up=result.is_up,
    )
    db.add(check)
    db.commit()
    db.refresh(check)
    return check


async def check_all_urls_async() -> None:
    db = SessionLocal()
    try:
        urls = [(url.id, url.url) for url in db.scalars(select(Url)).all()]
    finally:
        db.close()

    if not urls:
        return

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=REQUEST_TIMEOUT_SECONDS,
    ) as client:
        results = await asyncio.gather(
            *(fetch_url_status(client, url_id, url) for url_id, url in urls)
        )

    db = SessionLocal()
    try:
        db.add_all(
            Check(
                url_id=result.url_id,
                status_code=result.status_code,
                response_time_ms=result.response_time_ms,
                is_up=result.is_up,
            )
            for result in results
        )
        db.commit()
    finally:
        db.close()


def check_all_urls() -> None:
    asyncio.run(check_all_urls_async())



@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    scheduler.add_job(
        check_all_urls,
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
async def create_url(payload: UrlCreate, db: Session = Depends(get_db)) -> Url:
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
    result = await check_single_url(url.id, url.url)
    insert_check(db, result)
    return url


@app.get("/urls", response_model=list[UrlWithLatestCheck])
def list_urls(db: Session = Depends(get_db)) -> list[UrlWithLatestCheck]:
    urls = db.scalars(select(Url).order_by(Url.created_at.desc())).all()
    response = []

    for url in urls:
        recent_checks = db.scalars(
            select(Check)
            .where(Check.url_id == url.id)
            .order_by(Check.checked_at.desc(), Check.id.desc())
            .limit(10)
        ).all()
        
        latest_check = recent_checks[0] if recent_checks else None
        data = UrlWithLatestCheck.model_validate(url).model_dump()
        if latest_check:
            data.update(
                {
                    "status_code": latest_check.status_code,
                    "response_time_ms": latest_check.response_time_ms,
                    "is_up": latest_check.is_up,
                    "checked_at": latest_check.checked_at,
                }
            )
        data["recent_checks"] = recent_checks
        response.append(UrlWithLatestCheck(**data))

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
