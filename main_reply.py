"""
회의록 설명 1회 실행: 봇에 온 메시지를 처리해 답장.
스케줄러(예: 10~15분)가 이걸 호출.
  python main_reply.py
"""
import explainer

if __name__ == "__main__":
    explainer.run_once()
