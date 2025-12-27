from fastapi import FastAPI
from web_app.routes.feature import router as favorite_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # production環境要限制特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/")
def root():
    return {"msg": "Hello"}


app.include_router(favorite_router)