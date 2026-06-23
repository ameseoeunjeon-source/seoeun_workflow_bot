"""업무 다이제스트 메시지 구성."""
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def _now_str():
    return datetime.now(KST).strftime("%m/%d %H시 %M분")


def format_digest(result, unmatched):
    """result = {'rooms':[{'room','items':[...]}], 'has_new':bool}"""
    rooms = result.get("rooms", [])
    L = [f"🗂️ 업무 다이제스트 ({_now_str()})\n"]

    if not rooms:
        L.append("✅ 이번에 새로 떨어진 업무 없음")
    else:
        # 나에게 직접 떨어진 일 먼저 따로 모아 상단 강조
        mine = []
        for r in rooms:
            for it in r["items"]:
                if it["for_me"]:
                    mine.append((r["room"], it))
        if mine:
            L.append("🔴 나에게 떨어진 일")
            for room, it in mine:
                due = f" ⏰{it['due']}" if it["due"] else ""
                who = f" (요청: {it['from']})" if it["from"] else ""
                L.append(f"▸ [{room}] {it['task']}{due}{who}")
            L.append("")

        L.append("📋 방별 업무")
        for r in rooms:
            L.append(f"■ {r['room']}")
            for it in r["items"]:
                tag = "🔴" if it["for_me"] else "▫️"
                due = f" ⏰{it['due']}" if it["due"] else ""
                who = f" — {it['from']}" if it["from"] else ""
                L.append(f"  {tag} {it['task']}{due}{who}")
            L.append("")

    if unmatched:
        L.append("⚠️ 못 찾은 방(이름 교정 필요): " + ", ".join(unmatched))

    L.append("ℹ️ 모니터링 방의 최근 메시지에서 업무만 추출했습니다(사담 제외).")
    return "\n".join(L)


def split_for_telegram(text, limit=4000):
    if len(text) <= limit:
        return [text]
    chunks, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > limit:
            chunks.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur)
    return chunks
