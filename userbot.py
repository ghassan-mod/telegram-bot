import os, json, asyncio
from telethon import TelegramClient

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
session = os.getenv("SESSION_NAME")

client = TelegramClient(session, api_id, api_hash)

async def main():
    await client.start()
    print("UserBot started")

    while True:
        try:
            with open("send_queue.json", "r") as f:
                data = json.load(f)

            if not data:
                await asyncio.sleep(2)
                continue

            user_id = data["user_id"]
            app_id = data["app_id"]

            with open("apps.json", "r") as f:
                apps = json.load(f)

            app = apps.get(app_id)

            if app:
                await client.send_file(
                    user_id,
                    app["file_id"],
                    caption=f"تحميل {app['name']}"
                )

            with open("send_queue.json", "w") as f:
                json.dump({}, f)

        except Exception as e:
            print(e)

        await asyncio.sleep(3)

client.loop.run_until_complete(main())
