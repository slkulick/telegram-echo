from typing import Any

import threading
import requests

from fastapi import FastAPI, Request, Response
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from telegram import Update
from telegram.ext import Application, CallbackContext, CommandHandler, MessageHandler
from telegram._utils.types import JSONDict

TOKEN = "8280789096:AAEodpQBjc11bjQxMm6J95zmn3eO9eG9EnA"

class TelegramEchoBot:
    def __init__(self):
        self._application = Application.builder().token(TOKEN).updater(None).build()
        self._application.add_handler(CommandHandler("start", self._start_handler))
        self._application.add_handler(MessageHandler(None, self._message_handler))
       
    async def set_webhook(self, url: str):
        if not self._application.running:
            await self._application.bot.set_webhook(url=url, allowed_updates=Update.ALL_TYPES)
            await self._application.initialize()
            await self._application.start()
        
        return self._application.bot.get_webhook_info()

    async def post_update(self, data: JSONDict):
        await self._application.update_queue.put(
            Update.de_json(data=data, bot=self._application.bot)
        )

    async def shutdown(self) -> None:
        if self._application.running:
            await self._application.stop()
            await self._application.shutdown()

    async def _start_handler(self, update: Update, _: CallbackContext[Any, Any, Any, Any]) -> None:
        if update.message:
            await update.message.reply_html(text="Welcome to my echo bot!")

    async def _message_handler(self, update: Update, _: CallbackContext[Any, Any, Any, Any]) -> None:
        if update.message and update.message.text:
            await update.message.reply_html(text=update.message.text)
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
    app.state.telegram_bot = TelegramEchoBot()
    yield
    await app.state.telegram_bot.shutdown()
    app.state.keep_alive.shutdown()

app = FastAPI(lifespan=lifespan)

templates = Jinja2Templates(directory="templates")

@app.get("/")
async def get_root(request: Request):
    url = str(request.url)
    
    url = await app.state.telegram_bot.set_webhook(url)
    
    return templates.TemplateResponse(
        request=request, name="Index.html.j2", context={"url": url}
    )

@app.post("/")
async def post_root(request: Request):
    data = await request.json()
    await app.state.telegram_bot.post_update(data)
    return Response()

@app.get("/ping")
async def ping(request: Request):
    request.app.state.keep_alive.arm(str(request.url))
    return Response()
