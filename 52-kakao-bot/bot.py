#!/usr/bin/env python3
"""카카오톡 가족 단톡방 비서 봇 — 맥 카카오톡 앱을 kmsg 로 읽고 보낸다.

방을 몇 초마다 읽다가 '@봇이름' 으로 시작하는 새 글이 보이면
앞 대화와 함께 클로드에 묻고, 답을 같은 방에 보낸다.
멘션이 없는 글에는 답하지 않는다(토큰이 새지 않게).

비서 일 — 클로드가 답과 함께 할 일을 JSON 으로 돌려주면 봇이 실행한다.
  장보기 목록: 더하기 · 빼기 · 비우기(목록은 상태.json 에 남는다)
  알림: 정한 시각이 되면 봇이 먼저 방에 말을 건다
  요약·일정 정리·메뉴 추천: 답 글만

  python3 bot.py "방 이름" --name 아론AI

필요한 것: 맥용 카카오톡(봇 계정 로그인) · kmsg(brew install channprj/tap/kmsg,
손쉬운 사용 허용) · claude CLI(로그인) 또는 ANTHROPIC_API_KEY
"""
import argparse, json, os, re, subprocess, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
LOG = HERE / "기록.jsonl"
STATE = HERE / "상태.json"
WEEK = "월화수목금토일"

SYSTEM = """너는 가족 카카오톡 단톡방에 있는 비서 봇 '{name}'이다. '@{name}'은 너를 부른 표시다.
한국어로 짧게 답한다(다섯 줄 안, 목록이면 한 줄에 하나). 카톡은 마크다운을 안 보여 주니 ** · # 같은 표시를 쓰지 않는다. 모르는 것(날씨·뉴스 등 바깥 정보)은 모른다고 한다.
반드시 JSON 하나만 출력한다. 다른 글은 쓰지 않는다:
{{"reply": "방에 보낼 답",
  "shop_add": ["장보기 목록에 더할 것"], "shop_remove": ["뺄 것"], "shop_clear": false,
  "remind": [{{"at": "YYYY-MM-DD HH:MM", "text": "그 시각에 방에 보낼 알림 글"}}]}}
- 장보기 목록을 보여 달라면 지금 목록을 reply 에 쓴다. 더하거나 뺐으면 바뀐 뒤 목록을 reply 에 쓴다
- 알림은 '지금 시각' 기준으로 날짜를 정한다. 시각이 애매하면 묻고 remind 는 비운다
- 일정 정리·요약은 [앞 대화]에서만 뽑는다. 대화에 없는 일정을 지어내지 않는다"""


def kmsg(*args, timeout=60):
    r = subprocess.run(["kmsg", *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def read_room(room, limit):
    rc, out, err = kmsg("read", room, "--limit", str(limit), "--json", "--keep-window")
    if rc != 0:
        raise RuntimeError(err.strip() or out.strip())
    if not out.lstrip().startswith("{"):  # 방 창이 막 열려 글이 아직 안 보일 때
        return []
    d = json.loads(out)
    if d.get("chat") != room:  # kmsg 는 이름 일부만 맞아도 찾는다
        raise RuntimeError(f"다른 방을 읽음: {d.get('chat')}")
    return d["messages"]


OSA_PREVIEW = """tell application "System Events" to tell process "KakaoTalk"
repeat with r in rows of table 1 of scroll area 1 of window "카카오톡"
try
if value of static text 1 of UI element 1 of r is "%s" then return value of text area 1 of scroll area 1 of UI element 1 of r
end try
end repeat
return ""
end tell"""

OSA_REOPEN = """tell application "System Events" to tell process "KakaoTalk"
try
click (first button of window "%s" whose subrole is "AXCloseButton")
end try
delay 1
click button 2 of window "카카오톡"
delay 1
repeat with r in rows of table 1 of scroll area 1 of window "카카오톡"
try
if value of static text 1 of UI element 1 of r is "%s" then
perform action "AXShowMenu" of UI element 1 of r
delay 0.6
click menu item "채팅방 열기" of menu 1 of UI element 1 of r
exit repeat
end if
end try
end repeat
end tell"""


def osa(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
    return r.stdout.strip()


def fresh_read(room, limit):
    """오래 띄워 둔 방 창은 새 글을 그리지 않을 때가 있다(11-13 9:13 뒤 멈춤).
    채팅 목록의 마지막 글이 읽은 글 끝에 없으면 방 창을 닫았다 다시 연다."""
    msgs = read_room(room, limit)
    last = osa(OSA_PREVIEW % room)
    if last and not any(last[:15] in (m.get("body") or "") for m in msgs[-3:]):
        print("방 창이 멈춰 다시 엶 — 목록 마지막 글:", last[:30], flush=True)
        osa(OSA_REOPEN % (room, room))
        time.sleep(2)
        msgs = read_room(room, limit)
    return msgs


def send(room, text, dry):
    if dry:
        print("[보내지 않음]", text, flush=True)
        return True
    return kmsg("send", room, text, "--keep-window")[0] == 0


def ask_claude(prompt, model, system):
    t0 = time.time()
    if os.environ.get("ANTHROPIC_API_KEY"):
        body = json.dumps({"model": model, "max_tokens": 600, "system": system,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", body, {
            "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
            "content-type": "application/json"})
        d = json.load(urllib.request.urlopen(req, timeout=60))
        text = "".join(b.get("text", "") for b in d["content"])
        return text, {"via": "api", "usage": d.get("usage"), "sec": round(time.time() - t0, 2)}
    r = subprocess.run(["claude", "-p", prompt, "--model", model, "--append-system-prompt", system,
                        "--tools", "", "--setting-sources", "", "--strict-mcp-config",
                        "--output-format", "json"], capture_output=True, text=True, timeout=120, cwd="/tmp")
    d = json.loads(r.stdout)
    u = d.get("usage") or {}
    return d["result"], {"via": "claude-cli", "cost_usd": d.get("total_cost_usd"), "sec": round(time.time() - t0, 2),
                         "tokens": {k: u.get(k) for k in ("input_tokens", "cache_creation_input_tokens",
                                                           "cache_read_input_tokens", "output_tokens")}}


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else {"reply": text.strip()}
    except json.JSONDecodeError:
        return {"reply": text.strip()}


def load_state():
    try:
        return json.loads(STATE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"shop": [], "remind": []}


def save_state(s):
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1))


def now_text():
    n = datetime.now()
    return n.strftime("%Y-%m-%d %H:%M") + f" ({WEEK[n.weekday()]})"


def key(m):
    return (m.get("author"), m.get("time_raw"), m.get("body"))


def log(row):
    with LOG.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False), flush=True)


def due_reminders(a, state):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    left = []
    for r in state["remind"]:
        if r["at"] <= now:
            ok = send(a.room, "⏰ " + r["text"], a.dry_run)
            log({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": "알림", "due": r["at"], "text": r["text"], "sent": ok})
        else:
            left.append(r)
    if len(left) != len(state["remind"]):
        state["remind"] = left
        save_state(state)


def handle(a, m, msgs, i, state):
    got = time.time()
    body = (m.get("body") or "").strip()
    tag = next(t for t in a.tags if body.startswith(t))
    question = body[len(tag):].strip()
    history = "\n".join(f"{x.get('author')}: {x.get('body')}" for x in msgs[max(0, i - a.context):i])
    prompt = (f"[지금 시각] {now_text()}\n[장보기 목록] {', '.join(state['shop']) or '(비어 있음)'}\n"
              f"[잡아 둔 알림] {json.dumps(state['remind'], ensure_ascii=False)}\n"
              f"[앞 대화]\n{history}\n\n[{m.get('author')} 님이 너를 불렀다]\n{question}")
    raw, info = ask_claude(prompt, a.model, SYSTEM.format(name=a.name))
    d = parse(raw)
    if d.get("shop_clear"):
        state["shop"] = []
    state["shop"] = [x for x in state["shop"] if x not in (d.get("shop_remove") or [])]
    state["shop"] += [x for x in (d.get("shop_add") or []) if x not in state["shop"]]
    state["remind"] += [r for r in (d.get("remind") or []) if r.get("at") and r.get("text")]
    save_state(state)
    reply = (d.get("reply") or "").strip() or "음, 다시 한 번 말씀해 주세요."
    ok = send(a.room, reply, a.dry_run)
    log({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": "답", "room": a.room, "from": m.get("author"),
         "question": question, "reply": reply,
         "actions": {k: d.get(k) for k in ("shop_add", "shop_remove", "shop_clear", "remind") if d.get(k)},
         "llm": info, "sent": ok, "seen_to_sent_sec": round(time.time() - got, 2)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("room")
    ap.add_argument("--name", required=True, help="방에 보이는 봇 이름(멘션 글자)")
    ap.add_argument("--alias", action="append", default=[],
                    help="다른 이름으로도 부르면 답한다. 멘션 글자는 보내는 사람 폰에 저장된 친구 이름을 따른다")
    ap.add_argument("--every", type=float, default=3, help="몇 초마다 읽나")
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--context", type=int, default=30, help="앞 대화 몇 줄을 같이 보내나")
    ap.add_argument("--dry-run", action="store_true", help="보내지 않고 답만 찍는다")
    ap.add_argument("--catch-up", action="store_true",
                    help="켤 때 밀린 멘션(뒤에 봇 글이 없는 것)에 먼저 답한다")
    ap.add_argument("--from-start", action="store_true", help="이미 있던 멘션에도 답한다(시험용)")
    a = ap.parse_args()
    a.tags = ["@" + n for n in [a.name, *a.alias]]
    state = load_state()

    seen = {}  # 같은 글이 여러 번 올 수 있어 개수로 센다
    first = [] if a.from_start else fresh_read(a.room, 50)
    for m in first:
        seen[key(m)] = seen.get(key(m), 0) + 1
    if a.catch_up:
        for i, m in enumerate(first):
            mine_after = any(x.get("author") == "(me)" for x in first[i + 1:])
            if (m.get("body") or "").strip().startswith(tuple(a.tags)) and not mine_after:
                print("밀린 멘션:", m.get("author"), m.get("body"), flush=True)
                handle(a, m, first, i, state)
    print(f"듣는 중: {a.room} · {', '.join(a.tags)} 로 시작하는 글에만 답함", flush=True)

    while True:
        time.sleep(a.every)
        due_reminders(a, state)
        try:
            msgs = fresh_read(a.room, 50)
        except Exception as e:
            print("읽기 실패:", e, file=sys.stderr, flush=True)
            continue
        count = {}
        for i, m in enumerate(msgs):
            k = key(m)
            count[k] = count.get(k, 0) + 1
            if count[k] <= seen.get(k, 0):
                continue
            seen[k] = count[k]
            if (m.get("body") or "").strip().startswith(tuple(a.tags)):  # (me) 표시가 가끔 틀려 보낸 사람으로 거르지 않는다
                try:
                    handle(a, m, msgs, i, state)
                except Exception as e:
                    print("처리 실패:", e, file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
