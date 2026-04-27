import time
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path

import config

BASE_URL = "https://www.wanted.co.kr/api/v4/jobs"
DETAIL_URL = "https://www.wanted.co.kr/api/v4/jobs/{job_id}"
JOB_PAGE_URL = "https://www.wanted.co.kr/wd/{job_id}"
MASTER_CSV = Path(__file__).parent / "output" / "master.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.wanted.co.kr/",
}


def fetch_job_list() -> list[dict]:
    seen_ids: set[int] = set()
    all_jobs: list[dict] = []

    for keyword in config.KEYWORDS:
        print(f"  [>] 키워드: '{keyword}' 수집 중...")
        offset = 0
        for _ in range(config.MAX_PAGES_PER_KEYWORD):
            params = {
                "country": "kr",
                "job_sort": "job.latest_order",
                "years": config.EXPERIENCE_YEARS,
                "locations": config.LOCATIONS,
                "query": keyword,
                "limit": 20,
                "offset": offset,
            }
            try:
                resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json().get("data", [])
            except Exception as e:
                print(f"      [!] 요청 실패: {e}")
                break

            if not data:
                break

            for job in data:
                if job["id"] not in seen_ids:
                    seen_ids.add(job["id"])
                    all_jobs.append(job)

            if len(data) < 20:
                break

            offset += 20
            time.sleep(0.5)

    return all_jobs


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
        "first_seen": datetime.now().strftime("%Y-%m-%d"),
        "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def filter_entry_allowed(records: list[dict]) -> list[dict]:
    result = []
    for r in records:
        val = r.get("experience_from")
        if val == "" or val == 0 or val is None or (isinstance(val, float) and val == 0.0):
            result.append(r)
    return result


def find_new_jobs(records: list[dict]) -> list[dict]:
    if not MASTER_CSV.exists():
        return records

    master = pd.read_csv(MASTER_CSV)
    known_ids = set(master["job_id"].astype(int))
    return [r for r in records if int(r["job_id"]) not in known_ids]


def update_master(new_records: list[dict]):
    MASTER_CSV.parent.mkdir(exist_ok=True)
    df_new = pd.DataFrame(new_records)
    if MASTER_CSV.exists():
        df_master = pd.read_csv(MASTER_CSV)
        df_master = pd.concat([df_master, df_new], ignore_index=True)
    else:
        df_master = df_new
    df_master.to_csv(MASTER_CSV, index=False, encoding="utf-8-sig")


def save_new_csv(records: list[dict]) -> Path:
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    filepath = output_dir / f"new_{datetime.now().strftime('%Y%m%d')}.csv"
    pd.DataFrame(records).to_csv(filepath, index=False, encoding="utf-8-sig")
    return filepath


def main() -> list[dict]:
    print(f"[*] 수집 시작 / 키워드 {len(config.KEYWORDS)}개, 키워드당 최대 {config.MAX_PAGES_PER_KEYWORD}페이지")

    raw_jobs = fetch_job_list()
    print(f"[*] 전체 수집: {len(raw_jobs)}건 (키워드 중복 제거 후)")

    records = []
    for i, raw in enumerate(raw_jobs, 1):
        record = parse_job(raw)

        if config.FETCH_DETAIL:
            try:
                detail = fetch_detail(record["job_id"])
                record.update(detail)
                time.sleep(0.3)
            except Exception as e:
                print(f"    [!] 상세 수집 실패 (id={record['job_id']}): {e}")

        records.append(record)
        if i % 50 == 0:
            print(f"    ... {i}/{len(raw_jobs)}건 처리 중")

    filtered = filter_entry_allowed(records)
    print(f"[*] 신입 가능 공고: {len(filtered)}건 ({len(records)}건 중)")

    new_jobs = find_new_jobs(filtered)
    print(f"[*] 신규 공고: {len(new_jobs)}건 (master 대비)")

    if new_jobs:
        update_master(new_jobs)
        master_count = len(pd.read_csv(MASTER_CSV))
        print(f"[*] master.csv 업데이트 완료 (누적 {master_count}건)")

        filepath = save_new_csv(new_jobs)
        print(f"[+] 저장 완료 → {filepath}")
    else:
        print("[*] 신규 공고 없음 (신입 가능 + 미수집 기준) — 저장 생략")

    return new_jobs


if __name__ == "__main__":
    main()
