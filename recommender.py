import pandas as pd
from datetime import datetime
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import config
import profile as user_profile


def build_job_text(job: dict) -> str:
    return " ".join(filter(None, [
        str(job.get("title", "")),
        str(job.get("skills", "")),
        str(job.get("requirements", "")),
        str(job.get("preferred", "")),
        str(job.get("category", "")),
        str(job.get("main_tasks", "")),
    ]))


def build_profile_text() -> str:
    return " ".join(user_profile.SKILLS) + " " + user_profile.EXTRA_NOTES


def score_jobs(jobs: list[dict]) -> list[dict]:
    profile_text = build_profile_text()
    job_texts = [build_job_text(j) for j in jobs]

    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3))
    matrix = vectorizer.fit_transform([profile_text] + job_texts)
    sims = cosine_similarity(matrix[0:1], matrix[1:])[0]

    result = []
    for job, sim in zip(jobs, sims):
        score = round(float(sim) * 100, 1)
        job_text = build_job_text(job).lower()

        matched_skills = [s for s in user_profile.SKILLS if s.lower() in job_text]
        matched_certs  = [c for c in user_profile.CERTIFICATIONS if c.lower() in job_text]

        parts = []
        if matched_skills:
            parts.append(f"기술 일치: {', '.join(matched_skills)}")
        if matched_certs:
            parts.append(f"자격증 우대: {', '.join(dict.fromkeys(matched_certs))}")
        reason = " / ".join(parts) if parts else "텍스트 유사도 기반"

        result.append({**job, "score": score, "reason": reason})

    return sorted(result, key=lambda x: x["score"], reverse=True)


def save_recommended_csv(df: pd.DataFrame) -> Path:
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    filepath = output_dir / f"recommended_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    return filepath


def print_results(ranked: list[dict]):
    top = ranked[:config.TOP_N]
    print(f"\n[추천 결과] 신규 공고 상위 {config.TOP_N}개 ({len(ranked)}건 분석)")
    print("=" * 62)
    for rank, job in enumerate(top, 1):
        print(f"  {rank:2d}위  점수: {job['score']:5.1f}  {job['company']}")
        print(f"       직무: {job['title']}")
        print(f"       이유: {job['reason']}")
        print(f"       URL : {job['url']}")
        print()
    print("=" * 62)


def main(new_jobs: list[dict] | None = None):
    if new_jobs is None:
        today = datetime.now().strftime("%Y%m%d")
        path = Path(__file__).parent / "output" / f"new_{today}.csv"
        if not path.exists():
            print("[!] 오늘 신규 공고 파일 없음 — 크롤러를 먼저 실행하세요.")
            return
        new_jobs = pd.read_csv(path).to_dict("records")

    if not new_jobs:
        print("[*] 신규 공고가 없어 추천을 건너뜁니다.")
        return

    print(f"[*] TF-IDF 분석 중... ({len(new_jobs)}건)")
    ranked = score_jobs(new_jobs)

    print_results(ranked)

    filepath = save_recommended_csv(pd.DataFrame(ranked))
    print(f"[+] 저장 완료 → {filepath}")


if __name__ == "__main__":
    main()
