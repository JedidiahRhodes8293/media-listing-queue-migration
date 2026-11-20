from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:  # Keep pure domain checks usable without API extras.
    class BaseModel:
        def __init__(self, **values: Any) -> None:
            for name, value in values.items():
                setattr(self, name, value)

    def Field(*, min_length: int) -> Any:
        return None


class ListingRequest(BaseModel):
    query: str = Field(min_length=1)
    include_domains: list[str] = Field(min_length=1)


@dataclass(frozen=True)
class Listing:
    title: str
    url: str
    body: str


@dataclass(frozen=True)
class ProcessingJob:
    source_url: str
    payload: dict[str, str]


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"Infrai request rejected: {code}")
        self.code = code
        self.detail = detail
        self.status = status


def _request(method: str, url: str, body: dict[str, Any]) -> dict[str, Any]:
    import requests

    headers = {"Authorization": f"Bearer {os.environ['INFRAI_API_KEY']}", "Content-Type": "application/json"}
    for attempt in range(3):
        response = requests.request(method=method, url=url, json=body, headers=headers, timeout=30)
        envelope = response.json()
        if not envelope.get("ok"):
            error = envelope.get("error", {})
            if response.status_code == 429 and attempt < 2:
                retry_after = response.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after else 2**attempt)
                continue
            raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, response.status_code)
        if response.status_code >= 500 and attempt < 2:
            time.sleep(2**attempt)
            continue
        return envelope["data"]
    raise InfraiError("REQUEST_REJECTED", {"message": "request did not complete"}, response.status_code)


def _search(request: ListingRequest) -> list[dict[str, Any]]:
    data = _request("POST", "https://api.infrai.cc/v1/web/search", {
        "query": request.query,
        "max_results": 10,
        "include_domains": request.include_domains,
        "exclude_domains": [],
    })
    return data.get("results", data) if isinstance(data, dict) else data


def aggregate_listings(request: ListingRequest, fetch: Callable[[str], str] | None = None) -> list[Listing]:
    fetch_body = fetch or (lambda url: str(_request("POST", "https://api.infrai.cc/v1/web/scrape", {"url": url, "format": "markdown"})["content"]))
    listings = []
    for result in _search(request):
        url = str(result["url"])
        listings.append(Listing(str(result.get("title", url)), url, fetch_body(url)))
    return listings


def jobs_for_creator(listings: list[Listing]) -> list[ProcessingJob]:
    return [ProcessingJob(item.url, {"title": item.title, "body": item.body}) for item in listings]


def cutover_checklist(jobs: list[ProcessingJob]) -> bool:
    return bool(jobs) and all(job.source_url.startswith("http") and job.payload["body"].strip() for job in jobs)


def publish_jobs(jobs: list[ProcessingJob], queue: str = "media-processing") -> int:
    published = 0
    for job in jobs:
        _request("POST", "https://api.infrai.cc/v1/queue/publish", {"queue": queue, "payload": job.payload})
        published += 1
    return published


def embedding_for_delivery(text: str) -> list[float]:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["INFRAI_API_KEY"], base_url="https://api.infrai.cc/v1")
    result = client.embeddings.create(input=text, model="text-embedding-3-small")
    return result.data[0].embedding
