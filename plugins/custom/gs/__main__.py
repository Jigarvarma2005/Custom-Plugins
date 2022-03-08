# (c) @Jigarvarma2005
#Google search plugin for userge (Heroku Users)

import os
import requests
from userge import userge, Message

# Please don't steal this code.
GS_API_URL = os.environ.get("GS_API_URL","https://jv-api.deta.dev/google?query={squery}&limit={slimit}")


@userge.on_cmd("gs", about={
    'header': "do a Google search",
    'flags': {
        '-p': "page of results to return (default to 1)",
        '-l': "limit the number of returned results (defaults to 6)(max 10)"},
    'usage': "{tr}google [flags] [query | reply to msg]",
    'examples': "{tr}google -l10 github-userge"})
async def jv_gsearch(message: Message):
    query = message.filtered_input_str
    await message.edit(f"**Googling** for `{query}` ...")
    flags = message.flags
    limit = int(flags.get('-l', 6))
    if message.reply_to_message and not query:
        query = message.reply_to_message.text
    if not query:
        await message.err("Give a query or reply to a message to google!")
        return
    if limit >= 10:
        limit = 10
    da = requests.get(GS_API_URL.format(squery=query,slimit=limit)).json()
    res = da["result"]
    msg = ""
    for result in res:
        link = result["link"]
        title = result["title"]
        des = result["Description"]
        msg += f"[{title}]({link})\n`{des}`\n\n"
    if msg != "":
        await message.edit(text=f"**Search Query:**\n`{query}`\n\n**Results:**\n{msg}",
                           disable_web_page_preview=True,
                           parse_mode="Markdown")
    else:
        await message.edit("`The result parsing was unsuccessful. It is either your query could not be found or it was flagged as unusual traffic`")
