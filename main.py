from fastapi import FastAPI
from api.crud import router as crud_router
from api.router import router as routing_router

app = FastAPI()
app.include_router(crud_router, prefix="/__router-internal")
app.include_router(routing_router)

@app.get("/__internal/health")
def health():
    return {"ok": True}