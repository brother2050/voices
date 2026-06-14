#!/usr/bin/env python3
"""Batch TTS using MiMo-V2.5-TTS-VoiceDesign. Range-based for parallel execution."""

import csv, json, base64, os, sys, time, urllib.request
from urllib.error import HTTPError, URLError
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

API_KEY = os.environ.get("MIMO_API_KEY", "")
ENDPOINT = "https://api.xiaomimimo.com/v1/chat/completions"
MODEL = "mimo-v2.5-tts-voicedesign"
CSV_PATH = "./voices.csv"
WAV_DIR = "./voices_wav"
MAX_RETRIES = 3

LOG_DIR = './logs'
os.makedirs(LOG_DIR, exist_ok=True)

sys.stdout.reconfigure(line_buffering=True)
os.makedirs(WAV_DIR, exist_ok=True)

def build_voice_prompt(row):
    parts = []
    g = row.get('gender','').strip()
    a = row.get('age','').strip()
    if g and a: parts.append(f"{g}，{a}")
    elif g: parts.append(g)
    acc = row.get('accent','').strip()
    if acc: parts.append(acc)
    mood = row.get('mood','').strip()
    if mood: parts.append(f"语气{mood}")
    speed = row.get('speed','').strip()
    if speed: parts.append(speed)
    role = row.get('role','').strip()
    if role: parts.append(f"角色：{role}")
    return '，'.join(parts)

def synthesize(voice_prompt, text, output_path, eid=None):
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "user", "content": voice_prompt},
            {"role": "assistant", "content": text}
        ],
        "audio": {"format": "wav", "optimize_text_preview": False}
    }, ensure_ascii=False).encode('utf-8')

    # write request payload for debugging when eid provided
    if eid:
        try:
            with open(os.path.join(LOG_DIR, f'request_{eid}.json'), 'w', encoding='utf-8') as lf:
                lf.write(payload.decode('utf-8'))
        except Exception:
            pass

    req = urllib.request.Request(ENDPOINT, data=payload, headers={
        "api-key": API_KEY, "Content-Type": "application/json"
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
            result = json.loads(body)
            # save response body for debugging
            if eid:
                try:
                    with open(os.path.join(LOG_DIR, f'response_{eid}.json'), 'wb') as rf:
                        rf.write(body)
                except Exception:
                    pass
    except HTTPError as he:
        # capture response body for HTTP errors
        try:
            err_body = he.read().decode('utf-8', errors='replace')
        except Exception:
            err_body = '<unreadable response body>'
        # save error body
        if eid:
            try:
                with open(os.path.join(LOG_DIR, f'error_{eid}.txt'), 'w', encoding='utf-8') as ef:
                    ef.write(err_body)
            except Exception:
                pass
        raise RuntimeError(f"HTTPError {he.code}: {he.reason} - {err_body}")
    except URLError as ue:
        raise RuntimeError(f"URLError: {ue.reason}")

    if not result or 'choices' not in result:
        raise RuntimeError(f"Invalid response: {result}")

    try:
        audio_b64 = result['choices'][0]['message']['audio']['data']
    except Exception as e:
        raise RuntimeError(f"Missing audio data in response: {result}")

    audio_bytes = base64.b64decode(audio_b64)
    with open(output_path, 'wb') as f:
        f.write(audio_bytes)
    return len(audio_bytes)

def main():
    start_id = int(sys.argv[1])
    end_id = int(sys.argv[2])

    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        rows = [r for r in csv.DictReader(f) if start_id <= int(r['id']) <= end_id]

    total = len(rows)
    ok = 0; fail = 0; failed_ids = []

    for i, row in enumerate(rows):
        eid = row['id']
        safe = row['title'][:30].replace('/','_').replace('\\','_').replace(' ','_').replace('——','_')
        wav_path = os.path.join(WAV_DIR, f"{eid.zfill(3)}_{safe}.wav")

        if os.path.exists(wav_path) and os.path.getsize(wav_path) > 100:
            # print(f"[SKIP] ID={eid} already downloaded")
            ok += 1
            continue

        text = row['sample_text'].replace('**','').replace('##','').replace('`','')
        if len(text) > 500: text = text[:497]+'...'
        text = text.strip()
        if not text:
            print(f"[SKIP] ID={eid}"); fail += 1; continue

        voice = build_voice_prompt(row)
        print(f"[{i+1}/{total}] ID={eid} {row['title'][:35]}...", end=" ", flush=True)

        for attempt in range(MAX_RETRIES):
            try:
                size = synthesize(voice, text, wav_path, eid=eid)
                ok += 1
                print(f"✓ {size//1024}KB")
                break
            except Exception as e:
                err = str(e)[:80]
                if attempt < MAX_RETRIES-1:
                    print(f"retry({attempt+1}):{err}", end=" ", flush=True)
                    time.sleep(2*(attempt+1))
                else:
                    print(f"✗ {err}")
                    fail += 1
                    failed_ids.append(eid)
        time.sleep(0.3)

    print(f"\n[Worker {start_id}-{end_id}] Done: {ok} ok, {fail} fail")
    with open(f"./tts_w_{start_id}.json", 'w') as f:
        json.dump({"ok": ok, "fail": fail, "failed_ids": failed_ids}, f)

if __name__ == '__main__':
    main()
