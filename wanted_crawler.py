import time
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path

import config

BASE_URL = "https://www.wanted.co.kr/api/v4/jobs"
DETAIL_URL = "https://www.wanted.co.kr/api/v4/jobs/{job_id}"
JOB_PAGE_URL = "https://www.wanted.co.kr/wd/{job_id}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.wanted.co.kr/",
}


def fetch_job_list() -> list[dict]:
    jobs = []
    offset = 0
    limit = min(config.MAX_JOBS, 20)

    while len(jobs) < config.MAX_JOBS:
        params = {
            "country": "kr",
            "job_sort": "job.latest_order",
            "years": config.EXPERIENCE_YEARS,
            "locations": config.LOCATIONS,
            "limit": limit,
            "offset": offset,
        }
        if config.KEYWORDS:
            params["query"] = config.KEYWORDS[0]

        resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", [])

        if not data:
            break

        jobs.extend(data)
        offset += limit

        if len(data) < limit:
            break

        time.sleep(0.5)

    return jobs[: config.MAX_JOBS]


def fetch_detail(job_id: int) -> dict:
    resp = requests.get(
        DETAIL_URL.format(job_id=job_id), headers=HEADERS, timeout=10
    )
    resp.raise_for_status()
    detail = resp.json().get("job", {})
    d = detail.get("detail", {})
    return {
        "due_date": detail.get("due_time", ""),
        "main_tasks": d.get("main_tasks", ""),
        "requirements": d.get("requirements", ""),
        "preferred": d.get("preferred_points", ""),
        "benefits": d.get("benefits", ""),
    }


def parse_job(raw: dict) -> dict:
    company = raw.get("company", {})
    address = raw.get("address", {})
    category_tags = raw.get("category_tags", [])
    skill_tags = raw.get("skill_tags", [])

    return {
        "job_id": raw.get("id"),
        "title": raw.get("position", ""),
        "company": company.get("name", ""),
        "industry": company.get("industry_name", ""),
        "location": address.get("full_location", ""),
        "experience_from": raw.get("annual_from", ""),
        "experience_to": raw.get("annual_to", ""),
        "category": ", ".join(t.get("kind_name", "") for t in category_tags),
        "skills": ", ".join(t.get("title", "") for t in skill_tags),
        "due_date": "",
        "main_tasks": "",
        "requirements": "",
        "preferred": "",
        "benefits": "",
        "url": JOB_PAGE_URL.format(job_id=raw.get("id")),
        "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def save_csv(records: list[dict]) -> Path:
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    filename = output_dir / f"wanted_jobs_{datetime.now().strftime('%Y%m%d')}.csv"
    df = pd.DataFrame(records).drop_duplicates(subset="job_id")
    df.to_csv(filename, index=False, encoding="utf-8-sig")
    return filename


def main():
    print(f"[*] 수집 시작 / 키워드: {config.KEYWORDS or '전체'}, 경력: {config.EXPERIENCE_YEARS}년, 최대 {config.MAX_JOBS}건")

    raw_jobs = fetch_job_list()
    print(f"[*] {len(raw_jobs)}개 공고 수신")

    records = []
    for raw in raw_jobs:
        record = parse_job(raw)

        if config.FETCH_DETAIL:
            try:
                detail = fetch_detail(record["job_id"])
                record.update(detail)
                time.sleep(0.5)
            except Exception as e:
                print(f"    [!] 상세 수집 실패 (id={record['job_id']}): {e}")

        records.append(record)

    filepath = save_csv(records)
    print(f"[+] 저장 완료 → {filepath}  ({len(records)}건)")


if __name__ == "__main__":
    main()
