from fastapi import FastAPI

from app.api import announcements, companies, matching, eligibility

app = FastAPI(
    title="Doc집게 API",
    description="정부지원사업 자격요건 투명 검증 시스템",
    version="0.1.0",
)

app.include_router(announcements.router, prefix="/api/announcements", tags=["공고"])
app.include_router(companies.router, prefix="/api/companies", tags=["기업"])
app.include_router(matching.router, prefix="/api/matching", tags=["매칭"])
app.include_router(eligibility.router, prefix="/api/eligibility", tags=["자격요건"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
