import threading
import requests

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

class KeepAlive:
    _timer: threading.Timer | None = None
    _period_sec: float | None = None

    def __init__(self, period_sec: float=300):
        self._period_sec = period_sec
        
    def _trigger(self, url: str):
        requests.get(url)

    def arm(self, url: str):
        self.cancel()
            
        if self._period_sec:
            self._timer = threading.Timer(self._period_sec, self._trigger, args=(url, ))
            self._timer.start()

    def cancel(self, wait: bool=False):
        if self._timer and self._timer.is_alive():
            self._timer.cancel()
            if wait:
                self._timer.join()

    def shutdown(self):
        self._period_sec = None
        self.cancel(True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.keep_alive = KeepAlive()
    yield
    app.state.keep_alive.shutdown()

app = FastAPI(lifespan=lifespan)

templates = Jinja2Templates(directory="templates")

@app.get("/")
async def root_get(request: Request):
    return templates.TemplateResponse(
        request=request, name="Index.html.j2", context={"url": str(request.url)}
    )

@app.post("/")
async def root_post(request: Request):
    data = await request.body()
    print(data)

@app.get("/ping")
async def ping():
    return {"success": True}
