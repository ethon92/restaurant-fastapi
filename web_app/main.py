from fastapi import FastAPI
from web_app.routes.test import router

app = FastAPI()


@app.get("/")
def root():
    return {"msg": "Hello"}


app.include_router(router)