"""
인터랙티브 회의록 설명.
- 봇에게 온 메시지(텍스트/파일)를 getUpdates로 받아 Gemini가 설명/답변하고 답장.
- offset 으로 처리한 업데이트를 서버에서 소비(중복 답변 방지) → 별도 상태파일 불필요.
- 파일(docx/pdf/txt)도 받아 텍스트 추출 후 설명.
"""
import io
import re
import requests

import config
import llm

API = f"https://api.telegram.org/bot{config.BOT_TOKEN}"

_SYSTEM = (
    "너는 '" + config.MY_NAME + "'의 똑똑한 업무 비서다. 사용자가 회의록·업무 메시지·자료를 "
    "보내며 설명을 요청하면, 쉽고 명확하게 풀어준다. "
    "다음 순서로 정리하라:\n"
    "■ 한 줄 핵심\n"
    "■ 무슨 회의/내용인지 (맥락)\n"
    "■ 결정·합의된 것\n"
    "■ 할 일 (누가 / 무엇 / 언제)\n"
    "■ 어려운 용어·약어 풀이\n"
    "모르는 약어는 '아마 ~인 듯' 으로 추정 표시. 사실과 추측을 섞지 말 것. "
    "사용자가 일반 질문을 하면 비서답게 간결·정확하게 답하라. 한국어로.\n"
    "중요: 텔레그램에 보내는 거라 마크다운 기호를 절대 쓰지 마라. "
    "**굵게**, ##제목, `코드`, * 같은 기호 금지. 강조가 필요하면 기호 없이 문장으로. "
    "구분은 위처럼 ■ 또는 · 같은 글머리만 사용."
)

# 업무 다이제스트를 요청하는 말로 인식할 키워드
_DIGEST_TRIGGERS = ("다이제스트", "업무 정리", "업무정리", "업무 요약", "업무요약",
                    "할 일 정리", "오늘 업무", "방 요약", "업무 알려", "업무 뭐")


def _clean_md(t):
    """텔레그램 일반텍스트용: 마크다운 기호 제거(특히 ** 깨짐 방지)."""
    if not t:
        return t
    t = t.replace("**", "").replace("__", "").replace("`", "")
    t = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", t)      # ## 헤더 → 일반텍스트
    t = re.sub(r"(?m)^\s*[-*]\s+", "· ", t)           # - / * 글머리 → ·
    return t.strip()


def _is_digest_request(text):
    low = text.replace(" ", "")
    return any(k.replace(" ", "") in low for k in _DIGEST_TRIGGERS)


def _clear_webhook():
    """웹훅이 걸려 있으면 getUpdates가 막히므로 매번 해제(메시지 수신 보장)."""
    try:
        requests.post(f"{API}/deleteWebhook", timeout=15)
    except Exception as e:  # noqa
        print(f"[explainer] deleteWebhook 실패(무시): {e}")


def _get_updates(offset=None):
    params = {"timeout": 0}
    if offset is not None:
        params["offset"] = offset
    try:
        return requests.get(f"{API}/getUpdates", params=params, timeout=30).json()
    except Exception as e:  # noqa
        print(f"[explainer] getUpdates 실패: {e}")
        return {"result": []}


def _send(text, reply_to=None):
    from formatter import split_for_telegram
    for chunk in split_for_telegram(text):
        data = {"chat_id": config.CHAT_ID, "text": chunk,
                "disable_web_page_preview": True}
        if reply_to:
            data["reply_to_message_id"] = reply_to
            reply_to = None
        try:
            requests.post(f"{API}/sendMessage", data=data, timeout=30)
        except Exception as e:  # noqa
            print(f"[explainer] send 실패: {e}")


def _download_file(file_id):
    """봇 API로 파일 받아 bytes 반환."""
    try:
        r = requests.get(f"{API}/getFile", params={"file_id": file_id}, timeout=30).json()
        path = r["result"]["file_path"]
        url = f"https://api.telegram.org/file/bot{config.BOT_TOKEN}/{path}"
        return requests.get(url, timeout=60).content, path
    except Exception as e:  # noqa
        print(f"[explainer] 파일 다운로드 실패: {e}")
        return None, ""


def _extract_text(content, path):
    """docx/pdf/txt 에서 텍스트 추출."""
    low = path.lower()
    try:
        if low.endswith(".txt") or low.endswith(".md") or low.endswith(".csv"):
            return content.decode("utf-8", errors="ignore")
        if low.endswith(".docx"):
            import docx
            d = docx.Document(io.BytesIO(content))
            return "\n".join(p.text for p in d.paragraphs)
        if low.endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            return "\n".join((pg.extract_text() or "") for pg in reader.pages)
    except Exception as e:  # noqa
        print(f"[explainer] 텍스트 추출 실패: {e}")
    return ""


def _run_digest(reply_to):
    """봇에 '다이제스트 해줘' 요청 시: 지금 방들 긁어서 업무 정리해 답장."""
    import collector
    import extractor
    import formatter
    _send("🗂️ 업무방 확인 중… 잠시만요(1~2분).", reply_to=reply_to)
    try:
        rooms, unmatched = collector.collect()
        result = extractor.extract(rooms, ignore_state=True)  # 중복방지 무시, 현재 전부
        text = formatter.format_digest(result, unmatched)
    except Exception as e:  # noqa
        text = f"업무 다이제스트 생성 중 오류: {e}"
    _send(_clean_md(text))


def _handle(msg):
    chat = msg.get("chat", {})
    if str(chat.get("id")) != str(config.CHAT_ID):
        return  # 본인 채팅만
    mid = msg.get("message_id")
    text = (msg.get("text") or msg.get("caption") or "").strip()

    doc = msg.get("document")

    # 1) '다이제스트 해줘' 같은 요청 → 방 업무 정리 (파일 없을 때)
    if text and not doc and _is_digest_request(text):
        _run_digest(mid)
        return

    # 2) 회의록/질문 설명
    file_text = ""
    if doc:
        content, path = _download_file(doc.get("file_id"))
        if content:
            file_text = _extract_text(content, path)

    if not text and not file_text:
        return  # 설명할 내용 없음

    if file_text:
        user = (f"[사용자 메모/요청] {text or '이 자료 설명해줘'}\n\n"
                f"[첨부 문서 내용]\n{file_text[:12000]}")
    else:
        user = text

    if not llm.available():
        _send("⚠️ AI가 연결되지 않아 설명할 수 없어요. GEMINI_API_KEY 를 확인하세요.", reply_to=mid)
        return

    answer = llm.chat(_SYSTEM, user, max_tokens=2000, temperature=0.3)
    _send(_clean_md(answer) or "죄송해요, 답을 생성하지 못했어요. 다시 한 번 보내주세요.", reply_to=mid)


def run_once():
    """대기 중인 메시지를 모두 처리하고, 처리분을 소비(offset)한다."""
    if not config.BOT_TOKEN:
        print("[explainer] BOT_TOKEN 없음")
        return
    _clear_webhook()
    updates = _get_updates().get("result", [])
    if not updates:
        print("[explainer] 새 메시지 없음")
        return
    last = None
    for u in updates:
        last = u.get("update_id")
        msg = u.get("message") or u.get("edited_message")
        if msg:
            try:
                _handle(msg)
            except Exception as e:  # noqa
                print(f"[explainer] 처리 오류: {e}")
    # 처리한 업데이트 소비(다음 실행 때 다시 안 옴)
    if last is not None:
        _get_updates(offset=last + 1)
    print(f"[explainer] {len(updates)}건 처리")


if __name__ == "__main__":
    run_once()
