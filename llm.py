"""Google Gemini 호출 래퍼 (thinking 비활성 + RPM 보호). 주식봇과 동일 구조."""
import json
import time
import config

_client = None
_last_call = 0.0


def available():
    return config.LLM_ENABLED and bool(config.GEMINI_API_KEY)


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _throttle():
    global _last_call
    wait = config.LLM_MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def _cfg(sys_prompt, temperature, max_tokens):
    from google.genai import types
    kwargs = dict(system_instruction=sys_prompt, temperature=temperature,
                  max_output_tokens=max_tokens)
    try:
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    except Exception:  # noqa
        pass
    return types.GenerateContentConfig(**kwargs)


def chat(system, user, max_tokens=1500, temperature=0.3, want_json=False):
    if not available():
        return None
    sys_prompt = system
    if want_json:
        sys_prompt += "\n\n반드시 유효한 JSON 객체 하나만 출력하라. 코드펜스/설명 없이."
    cfg = _cfg(sys_prompt, temperature, max_tokens)
    for attempt in range(2):
        try:
            _throttle()
            resp = _get_client().models.generate_content(
                model=config.GEMINI_MODEL, contents=user, config=cfg)
            return (resp.text or "").strip()
        except Exception as e:  # noqa
            msg = str(e)
            if ("429" in msg or "RESOURCE_EXHAUSTED" in msg) and attempt == 0:
                print("[llm] 한도 초과 — 30초 대기 후 재시도")
                time.sleep(30)
                continue
            print(f"[llm] 실패: {e}")
            return None
    return None


def chat_json(system, user, max_tokens=2500):
    raw = chat(system, user, max_tokens=max_tokens, want_json=True)
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    s, e = raw.find("{"), raw.rfind("}")
    if s != -1 and e != -1 and e > s:
        raw = raw[s:e + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
