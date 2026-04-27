import json
import os
import anthropic
import pandas as pd
from datetime import datetime
from pathlib import Path

import config
import profile as user_profile

CLIENT = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = (
    "당신은 채용 컨설턴트입니다. "
    "사용자 프로필을 보고 각 공고의 적합도를 0~100으로 평가하세요. "
    "반드시 JSON 배열만 응답하세요. 다른 텍스트는 절대 포함하지 마세요.\n"
    "형식: [{\"job_id\": 숫자, \"score\": 숫자, \"reason\": \"한 줄 이유\"}]"
)


def build_user_prompt(jobs: list[dict]) -> str:
    lines = [
        "## 내 프로필",
        f"기술: {', '.join(user_profile.SKILLS)}",
        f"경력: 신입({user_profile.EXPERIENCE_YEARS}년)",
        f"선호 지역: {', '.join(user_profile.PREFERRED_LOCATIONS)}",
        f"선호 직무: {', '.join(user_profile.PREFERRED_CATEGORIES)}",
        f"비고: {user_profile.EXTRA_NOTES}",
        "",
        "## 평가할 공고 목록",
    ]
    for i, job in enumerate(jobs, 1):
        lines.append(
            f"{i}. [job_id={job['job_id']}] 회사: {job['company']} / 직무: {job['title']}"
        )
        if pd.notna(job.get("requirements")) and job.get("requirements"):
            lines.append(f"   자격요건: {str(job['requirements'])[:200]}")
        if pd.notna(job.get("preferred")) and job.get("preferred"):
            lines.append(f"   우대사항: {str(job['preferred'])[:150]}")
        if pd.notna(job.get("skills")) and job.get("skills"):
            lines.append(f"   기술태그: {job['skills']}")
        if pd.notna(job.get("location")) and job.get("location"):
            lines.append(f"   위치: {job['location']}")
    return "\n".join(lines)


def score_jobs(jobs: list[dict]) -> list[dict]:
    prompt = build_user_prompt(jobs)

    resp = CLIENT.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )

    raw = resp.content[0].text.strip()
    scores = json.loads(raw)
    return scores


def load_today_csv() -> pd.DataFrame:
    today = datetime.now().strftime("%Y%m%d")
    path = Path(__file__).parent / "output" / f"wanted_jobs_{today}.csv"
    if not path.exists():
        raise FileNotFoundError(f"오늘 수집 파일 없음: {path}")
    return pd.read_csv(path)


def save_recommended_csv(df: pd.DataFrame) -> Path:
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    filepath = output_dir / f"recommended_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    return filepath


def print_results(df: pd.DataFrame, total: int):
    top = df.head(config.TOP_N)
    print(f"\n[추천 결과] 상위 {config.TOP_N}개 공고 (총 {total}건 분석)")
    print("=" * 62)
    for rank, (_, row) in enumerate(top.iterrows(), 1):
        print(f"  {rank:2d}위  점수: {int(row['score']):3d}  {row['company']}")
        print(f"       직무: {row['title']}")
        print(f"       이유: {row['reason']}")
        print(f"       URL : {row['url']}")
        print()
    print("=" * 62)


def main():
    print("[*] 추천 분석 시작")
    df = load_today_csv()
    jobs = df.to_dict("records")

    print(f"[*] Claude API 분석 중... ({len(jobs)}건)")
    scores = score_jobs(jobs)

    score_map = {item["job_id"]: item for item in scores}
    df["score"] = df["job_id"].map(lambda jid: score_map.get(jid, {}).get("score", 0))
    df["reason"] = df["job_id"].map(lambda jid: score_map.get(jid, {}).get("reason", ""))
    df = df.sort_values("score", ascending=False).reset_index(drop=True)

    print_results(df, len(jobs))

    filepath = save_recommended_csv(df)
    print(f"[+] 저장 완료 → {filepath}")


if __name__ == "__main__":
    main()
