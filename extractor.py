"""
업무 추출 엔진.
- LLM이 방별 메시지에서 사담을 걸러내고 '업무/지시/요청/결정'을 추출.
- 특히 서은(MY_NAME)에게 떨어진 일을 표시.
- state.json 으로 이미 보고한 업무는 제외(DIGEST_MODE=new).
"""
import json
import hashlib
from datetime import datetime, timezone, timedelta

import config
import llm


# ----- 중복방지 상태 -----
def _load_state():
    if config.STATE_FILE.exists():
        try:
            return json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa
            return {}
    return {}


def _save_state(s):
    config.STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def _prune(s, days=3):
    cut = (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
    return {k: v for k, v in s.items() if v > cut}


_SYSTEM = (
    "너는 바쁜 직장인 '" + config.MY_NAME + "'의 업무 비서다. "
    "아래는 여러 업무 텔레그램 방의 최근 메시지다(발신자 포함). "
    "사담·인사·잡담은 모두 걸러내고, '실제 업무'만 골라내라: "
    "지시·요청·할 일·마감·의사결정·검토 요청·자료 요청·일정 등.\n"
    "특히 '" + config.MY_NAME + "'에게 직접 떨어진 일인지(나를 지목/멘션/리플) 구분하라.\n\n"
    "반드시 아래 JSON 으로만:\n"
    "{\n"
    '  "rooms": [\n'
    '    {"room": "방이름",\n'
    '     "items": [\n'
    '        {"task": "해야 할 일/논의된 업무를 한 문장으로 명확히",\n'
    '         "from": "지시·요청한 사람(발신자)",\n'
    '         "for_me": true/false (나에게 직접 떨어진 일이면 true),\n'
    '         "due": "기한 있으면(예: 내일 2시), 없으면 빈 문자열"}\n'
    "     ]}\n"
    "    ...업무가 있는 방만. 업무 없으면 그 방은 빼라\n"
    "  ]\n"
    "}\n\n"
    "규칙: 메시지에 실제로 있는 내용만. 추측으로 업무 만들지 말 것. "
    "사담만 있는 방은 결과에서 제외. task 는 구체적으로(누가 뭘 언제)."
)


def _build_input(rooms):
    parts = []
    for r in rooms:
        lines = [f"### 방: {r['room']}"]
        for m in r["messages"]:
            mark = " [←나에게 답글]" if m.get("reply_to_me") else ""
            lines.append(f"- {m['sender']}{mark}: {m['text'][:300]}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _item_hash(room, task):
    return hashlib.sha1(f"{room}|{task}".encode("utf-8")).hexdigest()[:16]


def extract(rooms, ignore_state=False):
    """
    반환: {"rooms":[{"room","items":[...]}], "has_new": bool}
    - 스케줄 실행: DIGEST_MODE=new 면 이미 보고한 업무는 빠진다.
    - ignore_state=True (봇에 '다이제스트 해줘' 요청 시): 중복방지 무시하고 현재 업무 전부 표시.
    """
    if not rooms or not llm.available():
        return {"rooms": [], "has_new": False}

    data = llm.chat_json(_SYSTEM, _build_input(rooms), max_tokens=3000)
    if not data or not isinstance(data, dict):
        return {"rooms": [], "has_new": False}

    state = _prune(_load_state())
    out_rooms = []
    has_new = False
    now = datetime.now(timezone.utc).timestamp()

    for r in data.get("rooms", []) or []:
        if not isinstance(r, dict):
            continue
        room = str(r.get("room", "")).strip()
        items = []
        for it in r.get("items", []) or []:
            if not isinstance(it, dict):
                continue
            task = str(it.get("task", "")).strip()
            if not task:
                continue
            if not ignore_state:
                h = _item_hash(room, task)
                is_new = h not in state
                if config.DIGEST_MODE == "new" and not is_new:
                    continue  # 이미 보고한 업무 스킵
                if is_new:
                    state[h] = now
                    has_new = True
            items.append({
                "task": task,
                "from": str(it.get("from", "")).strip(),
                "for_me": bool(it.get("for_me")),
                "due": str(it.get("due", "")).strip(),
            })
        if items:
            # 나에게 떨어진 일 먼저
            items.sort(key=lambda x: not x["for_me"])
            out_rooms.append({"room": room, "items": items})

    if not ignore_state:
        _save_state(state)
    return {"rooms": out_rooms, "has_new": has_new or (ignore_state and bool(out_rooms))}
