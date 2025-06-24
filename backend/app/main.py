from fastapi import FastAPI
from app.api import longterm_apis, shortterm_apis
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # consider restricting in production for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(longterm_apis.router, prefix="/longterm", tags=["longterm"])
app.include_router(shortterm_apis.router, prefix="/shortterm", tags=["shortterm"])
