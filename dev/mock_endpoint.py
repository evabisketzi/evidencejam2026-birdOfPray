"""MOCK streaming OpenAI-compatible endpoint for plumbing tests (NOT a model; scores from it mean nothing).  Usage: python dev/mock_endpoint.py PORT
Baseline prompt -> claim lines for up to 12 matching sentences; Socratic prompt (contains 'ask yourself') -> up to 9, plus one extra N line."""
import json, re, sys, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        if self.path != "/v1/chat/completions": self.send_response(404); self.end_headers(); return
        assert self.headers.get("Authorization", "").startswith("Bearer ")
        system, user = body["messages"][0]["content"], body["messages"][1]["content"]
        soc = "ask yourself" in system
        codes = re.findall(r"\bT(\d+)=", user)
        t1, t2 = ("T1", "T2" if "2" in codes else "T1") if codes else ("local seed source", "plant community")
        lines = []
        for m in re.finditer(r"^\[(\d+)\] \((\w+)\) (.*)$", user, re.M):
            k, sec, txt = int(m.group(1)), m.group(2), m.group(3).lower()
            if len(lines) >= (9 if soc else 12) or sec == "cap": continue
            if re.search(r"no significant|did not|not affect|no effect", txt): lines.append(f"N|{k}|{t1}/density/+|c|{t2}/cover|exp")
            elif re.search(r"decreas|reduc|suppress|lower|fewer", txt): lines.append(f"F|{k}|{t1}/density/+|c|{t2}/cover/-|D|exp|stage=seedling")
            elif re.search(r"increas|higher|greater|more", txt): lines.append(f"F|{k}|{t1}/density/+|ct|{t2}/height/+|U|obs")
        if soc and lines: lines.append(f"N|{(re.findall(r'^\[(\d+)\]', user, re.M) or ['1'])[0]}|{t1}/density/+|c|{t2}/richness|exp")
        text = "<think>x</think>\n" + "\n".join(lines) + "\n"
        usage = {"prompt_tokens": len(system + user) // 4, "completion_tokens": max(1, len(text) // 4)}
        time.sleep(0.3)
        if body.get("stream"):
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            for i in range(0, len(text), 40):
                self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": text[i:i+40]}}]}) + "\n\n").encode()); self.wfile.flush()
            if (body.get("stream_options") or {}).get("include_usage"):
                self.wfile.write(("data: " + json.dumps({"choices": [], "usage": usage}) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
        else:
            d = json.dumps({"choices": [{"message": {"content": text}}], "usage": usage}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(d))); self.end_headers(); self.wfile.write(d)

ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
