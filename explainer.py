"""
인터랙티브 회의록 설명.
- 봇에게 온 메시지(텍스트/파일)를 getUpdates로 받아 Gemini가 설명/답변하고 답장.
- offset 으로 처리한 업데이트를 서버에서 소비(중복 답변 방지) → 별도 상태파일 불필요.
- 파일(docx/pdf/txt)도 받아 텍스트 추출 후 설명.
"""
import io
import requests

import config
import llm

API = f"https://api.telegram.org/bot{config.BOT_TOKEN}"

_SYSTEM = (
    "너는 '" + config.MY_NAME + "'의 똑똑한 업무 비서다. 사용자가 회의록·업무 메시지·자료를 "
    "보내며 설명을 요청하면, 쉽고 명확하게 풀어준다. "
    "다음을 포함해 정리하라: (1) 한 줄 핵심, (2) 무슨 회의/내용인지 맥락, "
    "(3) 결정사항·합의된 것, (4) 액션아이템(누가 무엇을 언제), "
    "(5) 어려운 용어·약어 풀이. "
    "모르는 약어는 '아마 ~인 듯' 으로 추정 표시. 사실과 추측을 섞지 말 것. "
    "사용자가 일반 질문을 하면 비서답게 간결·정확하게 답하라. 한국어로."
)


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


def _handle(msg):
    chat = msg.get("chat", {})
    if str(chat.get("id")) != str(config.CHAT_ID):
        return  # 본인 채팅만
    mid = msg.get("message_id")
    text = (msg.get("text") or msg.get("caption") or "").strip()

    doc = msg.get("document")
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
    _send(answer or "죄송해요, 답을 생성하지 못했어요. 다시 한 번 보내주세요.", reply_to=mid)


def run_once():
    """대기 중인 메시지를 모두 처리하고, 처리분을 소비(offset)한다."""
    if not config.BOT_TOKEN:
        print("[explainer] BOT_TOKEN 없음")
        return
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
