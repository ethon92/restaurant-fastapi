from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()


@app.get("/")
def root():
    return {"msg": "Hello"}

# 在根路由上掛載靜態檔案
app.mount("/", StaticFiles(directory="public"), name="static")