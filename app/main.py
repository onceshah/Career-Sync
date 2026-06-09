from fastapi import FastAPI

app = FastAPI(
    title="AI Email Triage System",
    version="1.0.0"
)

@app.get("/")
def health_check():
    return {
        "status": "running",
        "service": "AI Email Triage System"
    }
