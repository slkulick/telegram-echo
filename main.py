import threading
import requests
from dataclasses import dataclass

from fastapi import FastAPI, Request, Response
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackContext, CommandHandler, TypeHandler
from telegram._utils.types import JSONDict

TOKEN = "8280789096:AAEodpQBjc11bjQxMm6J95zmn3eO9eG9EnA"

@dataclass
class WebhookUpdate:
    user_id: int
    payload: str

class TelegramEchoBot:
    def __init__(self):
        self._application = Application.builder().token(TOKEN).updater(None).build()
        self._application.add_handler(CommandHandler("start", self._start_handler))
        self._application.add_handler(TypeHandler(type=WebhookUpdate, callback=self._update_handler))
    
    async def start(self):
        await self._application.start()
    
    async def set_webhook(self, url: str) -> bool:
        return await self._application.bot.set_webhook(url=url, allowed_updates=Update.ALL_TYPES)

    async def post_update(self, data: JSONDict):
        await self._application.update_queue.put(
            Update.de_json(data=data, bot=self._application.bot)
        )

    async def shutdown(self) -> None:
        await self._application.shutdown()

    async def _start_handler(self, update: Update, context: CallbackContext) -> None:
        await update.message.reply_html(text="Welcome to my echo bot!")

    async def _update_handler(self, update: WebhookUpdate, context: CallbackContext) -> None:
        user_id = update.user_id
        payload = update.payload
        await context.bot.send_message(chat_id=user_id, text=payload, parse_mode=ParseMode.HTML)

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
    await app.state.telegram_bot.start()
    yield
    await app.state.telegram_bot.shutdown()
    app.state.keep_alive.shutdown()

app = FastAPI(lifespan=lifespan)

templates = Jinja2Templates(directory="templates")

@app.get("/")
async def get_root(request: Request):
    url = str(request.url)
    
    success = await app.state.telegram_bot.set_webhook(url)
    
    return templates.TemplateResponse(
        request=request, name="Index.html.j2", context={"url": url, "success": success}
    )

@app.post("/")
async def post_root(request: Request):
    data = await request.json()
    await app.state.telegram_bot.post_update(data)
    return Response()

@app.get("/ping")
async def ping(request: Request):
    request.app.state.keep_alive.arm(str(request.url))
    return {"success": True}
