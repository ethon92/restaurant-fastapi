from fastapi import FastAPI
from web_app.routes.feature import router as favorite_router

app = FastAPI()


@app.get("/")
def root():
    return {"msg": "Hello"}


app.include_router(favorite_router)