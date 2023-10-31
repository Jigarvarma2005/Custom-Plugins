#  (c) Jigarvarma2005 (Jigar Varma)
# Aria plugin for Userge
# inspired by https://github.com/jaskaranSM/UniBorg/blob/6d35cf452bce1204613929d4da7530058785b6b1/stdplugins/aria.py


from asyncio import sleep
from userge import userge, config as Config, Message
import math
import os
from pathlib import Path
from subprocess import PIPE, Popen
from requests import get
from userge.utils import progress, humanbytes
from userge.plugins.misc.upload.__main__ import upload_path
import aria2p
from fishhook import hook

LOGS = userge.getLogger(__name__)

def subprocess_run(cmd):
    subproc = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True, universal_newlines=True)
    talk = subproc.communicate()
    exitCode = subproc.returncode
    if exitCode != 0:
        return
    return talk

def rreplace(myStr):
    return myStr[::-1].replace("/","",1)[::-1]

#DOWN_PATH = rreplace(Config.Dynamic.DOWN_PATH)

def aria_start():
    trackers_list = get(
    "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt"
).text.replace("\n\n", ",")
    trackers = f"[{trackers_list}]"
    cmd = f"aria2c \
          --enable-rpc \
          --rpc-listen-all=false \
          --rpc-listen-port=6800 \
          --max-connection-per-server=10 \
          --rpc-max-request-size=1024M \
          --check-certificate=false \
          --follow-torrent=mem \
          --seed-time=0 \
          --max-upload-limit=1K \
          --max-concurrent-downloads=5 \
          --min-split-size=10M \
          --follow-torrent=mem \
          --split=10 \
          --bt-tracker={trackers} \
          --daemon=true \
          --allow-overwrite=true"
    process = subprocess_run(cmd)
    aria2 = aria2p.API(
        aria2p.Client(host="http://localhost", port=6800, secret="")
    )
    return aria2
    
aria2p_client = aria_start()


async def check_metadata(gid):
    t_file = aria2p_client.get_download(gid)
    return None if not t_file.followed_by_ids else t_file.followed_by_ids[0]


async def check_progress_for_dl(gid, message: Message, previous, tg_upload):  # sourcery no-metrics
    complete = False
    while not complete:
        try:
            t_file = aria2p_client.get_download(gid)
        except:
            return await message.edit("Download cancelled by user ...")
        complete = t_file.is_complete
        is_file = t_file.seeder
        try:
            if t_file.error_message:
                await message.err(str(t_file.error_message))
                LOGS.info(str(t_file.error_message))
                return
            if not complete:
                percentage = int(t_file.progress)
                downloaded = percentage * int(t_file.total_length) / 100
                prog_str = "Downloading ....\n[{0}{1}] {2}".format(
                    "".join(
                        Config.FINISHED_PROGRESS_STR
                        for _ in range(math.floor(percentage / 10))
                    ),
                    "".join(
                        Config.UNFINISHED_PROGRESS_STR
                        for _ in range(10 - math.floor(percentage / 10))
                    ),
                    t_file.progress_string(),
                )
                if is_file is None :
                   info_msg = f"**Connections**: `{t_file.connections}`\n"
                else :
                   info_msg = f"**Info**: `[ P : {t_file.connections} || S : {t_file.num_seeders} ]`\n"
                msg = (
                    f"`{prog_str}`\n"
                    f"**Name**: `{t_file.name}`\n"
                    f"**Completed**: {humanbytes(downloaded)}\n"
                    f"**Total**: {t_file.total_length_string()}\n"
                    f"**Speed**: {t_file.download_speed_string()} 🔻\n"
                    f"{info_msg}"
                    f"**ETA**: {t_file.eta_string()}\n"
                    f"**GID** : `{gid}`"
                )
                if msg != previous:
                    await message.edit(msg)
                    previous = msg
            elif complete and not t_file.name.lower().startswith("[metadata]"):
                return (
                    await upload_path(message, Path(t_file.name), False)
                    if tg_upload
                    else await message.edit(
                        f"**Name :** `{t_file.name}`\n"
                        f"**Size :** `{t_file.total_length_string()}`\n"
                        f"**Path :** `{os.path.join(t_file.dir, t_file.name)}`\n"
                        "**Response :** __Successfully downloaded...__"
                    )
                )
            else:
                await message.edit(f"`{msg}`")
            await sleep(Config.Dynamic.EDIT_SLEEP_TIMEOUT)
            await check_progress_for_dl(gid, message, previous, tg_upload)
        except Exception as e:
            if "not found" in str(e) or "'file'" in str(e):
                if "Your Torrent/Link is Dead." not in message.text:
                    await message.edit(f"**Download Canceled :**\n`{t_file.name}`")
            elif "depth exceeded" in str(e):
                t_file.remove(force=True)
                await message.edit(
                    f"**Download Auto Canceled :**\n`{t_file.name}`\nYour Torrent/Link is Dead."
                )




@userge.on_cmd("adownload", about={
    'header': "Download files to server from torrent or magnet using aria2p",
    'usage': "{tr}adownload [url/magnet | reply to torrent file]",
    'examples': "{tr}adownload https://speed.hetzner.de/100MB.bin"},
    check_downpath=True, del_pre=True)
async def t_url_download(message: Message):
    "Add url Into Queue."
    is_url = False
    tg_upload = '-t' in message.flags
    myoptions = {
             "dir": os.path.join("/app", Config.Dynamic.DOWN_PATH)
        }
    if (message.reply_to_message and 
           message.reply_to_message.document and 
           message.reply_to_message.document.file_name.lower().endswith(
            ('.torrent'))):
        resource = message.reply_to_message
        resource = await message.client.download_media(
            message=resource,
            file_name=Config.Dynamic.DOWN_PATH,
            progress=progress,
            progress_args=(message, "trying to download")
        )
        try:
            download = aria2p_client.add_torrent(
                resource, uris=None, options=myoptions, position=None
        )
        except Exception as e:
            return await message.err(str(e))
    elif message.input_str:
        resource = message.filtered_input_str
        is_url = True
        if resource.lower().startswith("http"):
            try:  # Add URL Into Queue
                resource = [resource]
                download = aria2p_client.add_uris(resource, options=myoptions)
            except Exception as e:
                return await message.err(str(e))
        elif resource.lower().startswith("magnet:"):
            try:  # Add Magnet Into Queue
                download = aria2p_client.add_magnet(resource, options=myoptions)
            except Exception as e:
                return await message.err(str(e))
    else:
        await message.edit("Reply to torrent file or send cmd with Magnet/URL.\n\nCheck `.help adownload`")
        return
    gid = download.gid
    await message.edit("`Processing......`")
    await check_progress_for_dl(gid=gid, message=message, previous="", tg_upload=tg_upload)
    await sleep(Config.Dynamic.EDIT_SLEEP_TIMEOUT)
    if is_url:
        file = aria2p_client.get_download(gid)
        if file.followed_by_ids:
            new_gid = await check_metadata(gid)
            await check_progress_for_dl(gid=new_gid, message=message, previous="", tg_upload=tg_upload)


@userge.on_cmd("aclear", about={
    'header': "Clear the aria Queue.",
    'description': "Clears the download queue, deleting all on-going downloads.",
    'usage': "{tr}aclear"})
async def remove_all(message):
    "Clear the aria Queue."
    removed = False
    try:
        removed = aria2p_client.remove_all(force=True)
        aria2p_client.purge()
    except Exception as e:
        message = await message.err({str(e)})
        await sleep(Config.Dynamic.EDIT_SLEEP_TIMEOUT)
    if not removed:  # If API returns False Try to Remove Through System Call.
        subprocess_run("aria2p remove-all")
    await message.edit("`Clearing on-going downloads... `")
    await sleep(1)
    await message.edit("`Successfully cleared all downloads.`")
    
@userge.on_cmd("acancel", about={
    'header': "Cancel a aria download.",
    'description': "Cancel a specific aria download",
    'usage': "{tr}acancel [gid]",
    'examples':'{tr}acancel nf5bgi7g'})
async def remove_a_download(message):
    "Clear the aria Queue."
    g_id = message.input_str
    try:
        downloads = aria2p_client.get_download(g_id)
    except:
        await message.edit("GID not found ....")
        return
    file_name = downloads.name
    aria2p_client.remove(downloads=[downloads], force=True, files=True, clean=True)
    await message.edit(f"Successfully cancelled download. \n\n`{file_name}`")


@userge.on_cmd("ashow", about={
        "header": "Shows current aria progress.",
        "description": "Shows progress of the on-going downloads.",
        "usage": "{tr}ashow",
    },
)
async def show_all(message):
    "Shows current aria progress of queue"
    downloads = aria2p_client.get_downloads()
    msg = ""
    for download in downloads:
        if str(download.status) != "complete":
            msg = (
            msg
            + "**File: **`"
            + str(download.name)
            + "`\n**Speed : **"
            + str(download.download_speed_string())
            + "\n**Progress : **"
            + str(download.progress_string())
            + "\n**Total Size : **"
            + str(download.total_length_string())
            + "\n**Status : **"
            + str(download.status)
            + "\n**ETA : **"
            + str(download.eta_string())
            + "\n**GID :**"
            + f"`{str(download.gid)}`"
            + "\n\n"
        )
    await message.edit("**On-going Downloads: **\n" + msg)
