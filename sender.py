"""업무 비서 봇으로 메시지 전송."""
import time
import requests
import config
from formatter import split_for_telegram


def send(text, disable_preview=True):
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    ok = True
    for chunk in split_for_telegram(text):
        try:
            r = requests.post(url, data={
                "chat_id": config.CHAT_ID, "text": chunk,
                "disable_web_page_preview": disable_preview,
            }, timeout=30)
            if r.status_code != 200:
                print(f"[sender] 실패 {r.status_code}: {r.text[:200]}")
                ok = False
            time.sleep(0.4)
        except Exception as e:  # noqa
            print(f"[sender] 예외: {e}")
            ok = False
    return ok


if __name__ == "__main__":
    print("테스트:", send("✅ 업무 비서 봇 연결 테스트"))
