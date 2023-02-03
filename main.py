import hashlib
import sys
import threading

import openai
import datetime

from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_handler_backends import State, StatesGroup
from telebot.asyncio_storage import StateMemoryStorage
from telebot import asyncio_filters
import telebot.types as types
from asgiref.sync import sync_to_async
import asyncio
from telebot import util
import emoji

TELEGRAM_TOKEN = "TELEGRAM BOT TOKEN"

openai.api_key = "OPENAI TOKEN"

working: list[int] = []


def log(message: str):
    time = datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=10))).strftime('[%d.%m.%Y / %H:%M]')
    with open("logs.txt", "a+") as f:
        f.write(f"{time} {message}\n")
        f.flush()
    f.close()


async def handle_response(message) -> str:
    response = await sync_to_async(openai.Completion.create)(
        model="text-davinci-003",
        prompt=message,
        temperature=0.9,
        max_tokens=2048,
        top_p=0.8,
        frequency_penalty=0.0,
        presence_penalty=0.0,
    )
    return response.choices[0].text


class AsyncClient(AsyncTeleBot, StatesGroup):
    getChatReply = State()

    def __init__(self, TOKEN) -> None:
        super().__init__(TOKEN, state_storage=StateMemoryStorage())


async def split_message(text, chat_id, client, code_block=False):
    working.remove(chat_id)
    splitted_text = util.smart_split(text, chars_per_string=3000)
    if code_block:
        for msg in splitted_text:
            await client.send_message(chat_id, "```" + msg + "```", parse_mode="markdown")
    else:
        for msg in splitted_text:
            await client.send_message(chat_id, msg)


async def send_message(message: types.Message, client: AsyncClient, followup=False):
    await client.send_message(chat_id=message.chat.id, text="✅Запрос отправлен, дождитесь ответа.\n" +
                                                            "В среднем, ответ занимает от одной минуты до пяти.")
    working.append(message.chat.id)
    chat_id = message.chat.id
    try:
        if followup:
            question = message.text
        else:
            question = message.text.split("/chat ", 1)[1]
        log("Отправлен от: " + message.from_user.username + " | " + question)
        response = "\n".join(f"{await handle_response(question)}".split("\n\n"))
        if "```" in response:
            parts = response.split("```")
            code_flag = 0
            for part in parts:
                if not (code_flag % 2):
                    await split_message(part, chat_id, client)
                else:
                    await split_message(part, chat_id, client, True)
                code_flag += 1
        else:
            await split_message(response, chat_id, client)
    except Exception as e:
        print(e)
        await client.send_message(message.chat.id, "> Ошибка. Лог отправлен владельцу.")


checked: bool = False


def run_tele_bot():
    BOT_TOKEN = TELEGRAM_TOKEN
    client = AsyncClient(BOT_TOKEN)

    @client.message_handler()
    async def chat(message: types.Message):
        if message.text.startswith("/start"):
            start_msg = emoji.emojize(
                f':robot: Чтобы начать пользоваться, напиши /chat <запрос без кавычек>, или просто /chat, ' +
                'или вообще просто обычным запросом.' + '\nВ запросе уточняйте свой вопрос, чтобы бот понял о чем вы')
            await client.reply_to(message, start_msg, parse_mode="markdown")
            return
        if not working.__contains__(message.chat.id):
            if len(message.text) < 5:
                await client.send_message(message.chat.id, "Запрос не должен быть меньше 5 символов.")
                return
            if message.text.startswith("/chat"):
                if message.text.split("/chat")[1] in ['', ' ']:
                    await client.set_state(message.from_user.id, AsyncClient.getChatReply, message.chat.id)
                    await client.send_message(message.chat.id, 'Введи сообщение:')
                else:
                    await send_message(message, client)
            else:
                await client.set_state(message.from_user.id, AsyncClient.getChatReply, message.chat.id)
                await send_message(message, client, followup=True)
        else:
            await client.send_message(message.chat.id, "Вы уже отправили запрос на обработку.")

    @client.message_handler(state=AsyncClient.getChatReply)
    async def chat_followup(message: types.Message):
        await send_message(message, client, followup=True)
        await client.delete_state(message.from_user.id, message.chat.id)

    client.add_custom_filter(asyncio_filters.StateFilter(client))
    asyncio.run(client.infinity_polling())


run_tele_bot()
