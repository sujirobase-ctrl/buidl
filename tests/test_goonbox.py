"""Regression guard: goonbox.cr resolver + HOSTS entry (mirrors ForumPostDownloader).

Not the suite. Exercises the new _resolve_goodbox against the live API and the
HOSTS matcher in parse_hosts. Mocks nothing (real HTTP + cookies).
"""
import sys
sys.path.insert(0, r"C:\Users\isaac\Downloads\buidl")

from src.http_client import HttpClient
from src.resolvers import resolve
from src.parsers.host_parser import parse_hosts

res = []
c = HttpClient(cookies_file=r"C:\Users\isaac\Downloads\cookies.txt")
REAL = "aVhBYYe"  # confirmed live goonbox img id from the nene thread

# HOSTS matcher
html = f'<a href="https://goonbox.cr/img/{REAL}">x</a>'
m = parse_hosts(html)
assert any("goonbox.cr" in x.url for x in m), "goonbox.cr not matched"
res.append("HOSTS: goonbox.cr/img/<id> detected by parse_hosts")

# resolver -> real image url on cuckcapital.cr
out = resolve(f"https://goonbox.cr/img/{REAL}", c)
assert len(out) == 1, out
assert ".jpg" in out[0].url or ".png" in out[0].url, out[0].url
res.append(f"resolver: {out[0].filename} -> {out[0].url[:60]}...")

# album form
out2 = resolve("https://goonbox.cr/a/someSlug", c)
res.append(f"album form accepted (returns list, len={len(out2)})")

# bad id -> [] (safe)
assert resolve("https://goonbox.cr/img/zzz_nope", c) == []
res.append("unknown id -> [] (no exception)")

print("GOONBOX tests — passed:")
for r in res:
    print("  OK", r)
print(f"({len(res)} checks)")
