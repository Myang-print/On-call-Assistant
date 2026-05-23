from fastapi import FastAPI


app = FastAPI(title="On-Call Assistant")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
