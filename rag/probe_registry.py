# -*- coding: utf-8 -*-
"""探测 registry.ollama.ai 的模型层下载速度，判断是否可用 ollama pull。"""
import json
import time
import urllib.request
import urllib.error
import urllib.parse
import re

MODEL = "qwen2.5"
TAG = "7b"
BASE = "https://registry.ollama.ai/v2/library/%s" % MODEL


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    return urllib.request.urlopen(req, timeout=40)


def bearer_token(auth_header):
    m = re.search(r'realm="([^"]+)"', auth_header or "")
    if not m:
        return None
    realm = m.group(1)
    q = {}
    for key in ("service", "scope"):
        mm = re.search(key + r'="([^"]+)"', auth_header or "")
        if mm:
            q[key] = mm.group(1)
    url = realm + ("?" + urllib.parse.urlencode(q) if q else "")
    return json.load(get(url))["token"]


token = None
try:
    man = json.load(get(BASE + "/manifests/" + TAG))
except urllib.error.HTTPError as e:
    if e.code == 401:
        token = bearer_token(e.headers.get("WWW-Authenticate"))
        print("取得 token:", "OK" if token else "FAIL")
        man = json.load(get(BASE + "/manifests/" + TAG,
                            {"Authorization": "Bearer " + token}))
    else:
        raise

layers = man.get("layers", [])
sizes = {}
for l in layers:
    sizes[l["digest"]] = l.get("size", 0)
biggest = max(sizes, key=sizes.get)
print("manifest OK, layers:", len(layers))
print("最大层:", biggest[:20], round(sizes[biggest] / 1048576, 1), "MB")

# 下载 15 秒测速
url = BASE + "/blobs/" + biggest
headers = {"Authorization": "Bearer " + token} if token else {}
req = urllib.request.Request(url, headers=headers)
t0 = time.time()
got = 0
try:
    r = urllib.request.urlopen(req, timeout=40)
    while time.time() - t0 < 15:
        chunk = r.read(262144)
        if not chunk:
            break
        got += len(chunk)
except Exception as e:
    print("read stop:", e)
el = time.time() - t0
kbps = got / 1024 / el if el > 0 else 0
print(f"15s 内下载 {got/1048576:.2f} MB => ~{kbps:.0f} KB/s")
total_mb = sizes[biggest] / 1048576
if kbps > 0:
    print(f"该层总大小 {total_mb:.0f} MB，预估耗时 {total_mb*1024/kbps/60:.1f} 分钟")
    print("结论:", "可用 ollama pull" if kbps > 200 else "过慢，建议改用 hf-mirror 导 GGUF")
