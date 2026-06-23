"""
업무방 메시지 수집 (Telethon, 세션 재활용).
지난 LOOKBACK_MINUTES 분 동안 각 방의 메시지를 발신자 이름과 함께 모은다.

반환: (rooms, unmatched)
  rooms = [{"room": 방이름, "messages": [{"sender","text","date","reply_to_me"}...]}]
  unmatched = 못 찾은 방 식별자 목록
"""
import asyncio
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

import config


def _make_client():
    if config.TG_SESSION_STRING:
        return TelegramClient(StringSession(config.TG_SESSION_STRING),
                              config.TG_API_ID, config.TG_API_HASH)
    return TelegramClient(config.SESSION_NAME, config.TG_API_ID, config.TG_API_HASH)


def _norm(s):
    return "".join((s or "").split()).lower()


async def _collect_async():
    wanted = config.load_rooms()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=config.LOOKBACK_MINUTES)

    client = _make_client()
    await client.start(phone=config.TG_PHONE)

    # 대화목록 캐시
    by_id, by_title = {}, {}
    async for d in client.iter_dialogs():
        by_id[d.id] = d.entity
        title = getattr(d.entity, "title", None)
        if title:
            by_title[_norm(title)] = d.entity

    me = await client.get_me()
    my_id = me.id

    rooms, unmatched = [], []
    for w in wanted:
        entity = None
        if isinstance(w, int):
            entity = by_id.get(w)
            if entity is None:
                try:
                    entity = await client.get_entity(w)
                except Exception:  # noqa
                    entity = None
        else:
            entity = by_title.get(_norm(w))
            if entity is None:
                # 부분일치 시도
                for t, ent in by_title.items():
                    if _norm(w) in t or t in _norm(w):
                        entity = ent
                        break
        if entity is None:
            unmatched.append(str(w))
            continue

        title = getattr(entity, "title", str(w))
        msgs = []
        try:
            async for m in client.iter_messages(entity, limit=config.MAX_MSGS_PER_ROOM):
                if m.date < cutoff:
                    break
                text = (m.message or "").strip()
                if not text:
                    continue
                sender = ""
                try:
                    s = await m.get_sender()
                    sender = getattr(s, "first_name", None) or getattr(s, "title", None) or ""
                    if getattr(s, "last_name", None):
                        sender += " " + s.last_name
                except Exception:  # noqa
                    pass
                reply_to_me = False
                try:
                    if m.reply_to_msg_id:
                        rm = await m.get_reply_message()
                        if rm and rm.sender_id == my_id:
                            reply_to_me = True
                except Exception:  # noqa
                    pass
                msgs.append({
                    "sender": sender.strip() or "(알수없음)",
                    "text": text, "date": m.date, "reply_to_me": reply_to_me,
                })
        except FloodWaitError as e:
            print(f"[collector] FloodWait {e.seconds}s")
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:  # noqa
            print(f"[collector] {title} 오류: {e}")

        if msgs:
            msgs.reverse()  # 시간순(오래된→최신)
            rooms.append({"room": title, "messages": msgs})

    await client.disconnect()
    return rooms, unmatched


def collect():
    return asyncio.run(_collect_async())


if __name__ == "__main__":
    r, u = collect()
    print(f"수집 방 {len(r)}개, 못찾음 {len(u)}개: {u}")
    for room in r:
        print(f"  [{room['room']}] 메시지 {len(room['messages'])}개")
