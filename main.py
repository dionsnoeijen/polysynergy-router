from fastapi import FastAPI
from api.crud import router as crud_router
from api.router import router as routing_router

app = FastAPI()
app.include_router(crud_router)
app.include_router(routing_router)

