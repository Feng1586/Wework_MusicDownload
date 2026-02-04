from fastapi import FastAPI
from router import wechat_verify

app = FastAPI()
app.include_router(wechat_verify.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)