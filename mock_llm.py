"""Mock OpenAI-compatible chat endpoint: scripted agent for testing perturbation injection.
Steps 1..N-1 call a harmless tool; step N calls claim_done. Logs every request's messages."""
import json, sys, itertools
from http.server import BaseHTTPRequestHandler, HTTPServer

N_STEPS = int(sys.argv[2]); LOG = sys.argv[3]
counter = itertools.count(1)

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        n = next(counter)
        names = [t['function']['name'] for t in body.get('tools', [])]
        with open(LOG, 'a') as f:
            f.write(json.dumps({"call": n, "tools": names, "messages": body['messages']}) + "\n")
        done = [x for x in names if 'claim_done' in x]
        safe = [x for x in names if 'claim_done' not in x]
        lst = [x for x in safe if 'python_execute' in x] or safe
        name = done[0] if (n >= N_STEPS and done) else lst[0]
        msg = {"role": "assistant", "content": None,
               "tool_calls": [{"id": f"call_{n}", "type": "function",
                               "function": {"name": name, "arguments": json.dumps({"code": "print(1)"}) if "python_execute" in name else "{}"}}]}
        out = {"id": f"x{n}", "object": "chat.completion", "model": "mock",
               "choices": [{"index": 0, "message": msg, "finish_reason": "tool_calls"}],
               "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
        data = json.dumps(out).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)

HTTPServer(('127.0.0.1', int(sys.argv[1])), H).serve_forever()