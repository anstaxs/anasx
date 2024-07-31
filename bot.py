import asyncio
import re
import aioschedule
import sqlite3
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor

API_TOKEN = '6484608271:AAEc7vYgjZZwZthNZILaSodxZHVXOcc-ZdM'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

conn = sqlite3.connect('reminders.db')
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        reminder_time TEXT,
        message TEXT
    )
''')
conn.commit()

async def send_reminder(chat_id: int, message: str):
    await bot.send_message(chat_id=chat_id, text=message)

async def schedule_reminder():
    while True:
        now = datetime.now()
        # Нагадування за 1 годину до призначеного часу
        reminder_time_check = (now + timedelta(hours=1)).strftime("%Y/%m/%d %H:%M")
        c.execute('SELECT chat_id, message FROM reminders WHERE reminder_time = ?', (reminder_time_check,))
        reminders = c.fetchall()
        for chat_id, message in reminders:
            await send_reminder(chat_id, message)
        await aioschedule.run_pending()
        # Частота перевірки кожні 30 секунд
        await asyncio.sleep(30)

@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    await message.reply('''
Привіт! Я бот-планувальник. Використовуйте команду /set "дата у форматі РРРР/ММ/ДД ЧЧ:ММ" "повідомлення" для встановлення нагадування.
Використовуйте команду /list для перегляду всіх завдань.
Використовуйте команду /delete <ID> для видалення нагадування.
''')

@dp.message_handler(commands=['set'])
async def set_reminder(message: types.Message):
    try:
        command = message.text
        match = re.match(r'/set (\d{4}/\d{2}/\d{2} \d{2}:\d{2}) "(.+)"', command)
        if not match:
            await message.reply(
                'Неправильний формат команди. Використовуйте: /set "дата у форматі РРРР/ММ/ДД ЧЧ:ММ" "повідомлення"')
            return

        reminder_time_str = match.group(1)
        reminder_message = match.group(2)
        reminder_time = datetime.strptime(reminder_time_str, "%Y/%m/%d %H:%M")
        if reminder_time <= datetime.now() + timedelta(hours=1):
            await message.reply("Час нагадування повинен бути через більше ніж одну годину.")
            return

        c.execute('INSERT INTO reminders (chat_id, reminder_time, message) VALUES (?, ?, ?)', (message.chat.id, reminder_time_str, reminder_message))
        conn.commit()

        await message.reply(f"Нагадування встановлено на {reminder_time_str} з повідомленням: {reminder_message}")
    except IndexError as e1:
        print(e1)
        await message.reply('Неправильний формат команди. Використовуйте: /set "дата у форматі РРРР/ММ/ДД ЧЧ:ММ" "повідомлення"')
    except ValueError as e:
        print(e)
        await message.reply('Неправильний формат дати або часу. Використовуйте: /set "дата у форматі РРРР/ММ/ДД ЧЧ:ММ" "повідомлення"')

@dp.message_handler(commands=['list'])
async def list_reminders(message: types.Message):
    c.execute('SELECT id, reminder_time, message FROM reminders WHERE chat_id = ?', (message.chat.id,))
    reminders = c.fetchall()
    if reminders:
        reminders_text = '\n'.join([f"{id} - {time} - {msg}" for id, time, msg in reminders])
        await message.reply(f"Ваші нагадування:\n{reminders_text}")
    else:
        await message.reply("У вас немає встановлених нагадувань.")

@dp.message_handler(commands=['delete'])
async def delete_reminder(message: types.Message):
    try:
        reminder_id = int(message.text.split()[1])
        c.execute('DELETE FROM reminders WHERE id = ? AND chat_id = ?', (reminder_id, message.chat.id))
        if c.rowcount == 0:
            await message.reply("Нагадування з таким ID не знайдено.")
        else:
            conn.commit()
            await message.reply(f"Нагадування з ID {reminder_id} видалено.")
    except (IndexError, ValueError):
        await message.reply("Неправильний формат команди. Використовуйте: /delete <ID>")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(schedule_reminder())
    executor.start_polling(dp, skip_updates=True)
