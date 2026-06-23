"""
업무 다이제스트 1회 실행: 방 수집 → 업무 추출 → 전송.
스케줄러(예: 30~60분)가 이걸 호출.
  python main_digest.py
"""
import traceback

import config
import collector
import extractor
import formatter
import sender


def run_once():
    errs = config.validate()
    if errs:
        msg = "⚠️ 설정 오류:\n" + "\n".join(f"- {e}" for e in errs)
        print(msg)
        if config.BOT_TOKEN and config.CHAT_ID:
            try:
                sender.send(msg)
            except Exception:  # noqa
                pass
        return

    try:
        rooms, unmatched = collector.collect()
    except Exception as e:  # noqa
        print("수집 실패:", e)
        traceback.print_exc()
        sender.send(f"⚠️ 업무방 수집 오류: {e}")
        return
    print(f"수집 방 {len(rooms)}개, 못찾음 {len(unmatched)}")

    try:
        result = extractor.extract(rooms)
    except Exception as e:  # noqa
        print("추출 실패:", e)
        traceback.print_exc()
        return

    # new 모드: 새 업무도 없고 못찾은 방도 없으면 침묵
    if config.DIGEST_MODE == "new" and not result["has_new"] and not unmatched:
        print("새 업무 없음 → 전송 안 함")
        return

    text = formatter.format_digest(result, unmatched)
    sender.send(text)
    print("다이제스트 전송 완료")


if __name__ == "__main__":
    run_once()
