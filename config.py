"""환경설정 로더 (.env)."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _int(key, default):
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return int(default)


def _bool(key, default="false"):
    return os.getenv(key, default).strip().lower() in ("1", "true", "yes", "on")


# 텔레그램 개인 계정 (재활용)
TG_API_ID = _int("TG_API_ID", 0)
TG_API_HASH = os.getenv("TG_API_HASH", "")
TG_PHONE = os.getenv("TG_PHONE", "")
TG_SESSION_STRING = os.getenv("TG_SESSION_STRING", "")
SESSION_NAME = str(BASE_DIR / "work_session")

# 업무 비서 봇 (새 봇)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")

# LLM
LLM_ENABLED = _bool("LLM_ENABLED", "true")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
LLM_MIN_INTERVAL = _int("LLM_MIN_INTERVAL", 7)

# 파라미터
LOOKBACK_MINUTES = _int("LOOKBACK_MINUTES", 90)
MAX_MSGS_PER_ROOM = _int("MAX_MSGS_PER_ROOM", 120)
DIGEST_MODE = os.getenv("DIGEST_MODE", "new").strip().lower()

# 사용자 본인 식별(업무가 '나'에게 떨어졌는지 판단용)
MY_NAME = os.getenv("MY_NAME", "서은")

ROOMS_FILE = BASE_DIR / "rooms.txt"
STATE_FILE = BASE_DIR / "state.json"


def load_rooms():
    """rooms.txt → [(식별자, 표시용원문)]. 식별자는 int(ID) 또는 str(이름)."""
    if not ROOMS_FILE.exists():
        return []
    out = []
    for line in ROOMS_FILE.read_text(encoding="utf-8").splitlines():
        raw = line.split("#", 1)[0].strip()
        if not raw:
            continue
        token = raw.replace("https://", "").replace("http://", "").replace("t.me/", "").lstrip("@")
        try:
            out.append(int(token))
        except ValueError:
            out.append(token)
    return out


def validate():
    errs = []
    if not TG_API_ID:
        errs.append("TG_API_ID 가 비어 있습니다")
    if not TG_API_HASH:
        errs.append("TG_API_HASH 가 비어 있습니다")
    if not TG_SESSION_STRING:
        errs.append("TG_SESSION_STRING 이 비어 있습니다 (주식봇 값 재활용)")
    if not BOT_TOKEN:
        errs.append("BOT_TOKEN 이 비어 있습니다 (새 봇)")
    if not CHAT_ID:
        errs.append("CHAT_ID 가 비어 있습니다")
    if LLM_ENABLED and not GEMINI_API_KEY:
        errs.append("GEMINI_API_KEY 가 비어 있습니다")
    if not load_rooms():
        errs.append("rooms.txt 에 업무방이 없습니다")
    return errs
