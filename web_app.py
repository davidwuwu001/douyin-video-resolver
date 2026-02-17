"""抖音视频解析 Web 服务

轻量 Flask 应用，提供网页界面和 API 接口。
输入分享文本/短链接/长链接，解析出无水印下载地址。

启动方式: python web_app.py
访问: http://localhost:8080
"""

import logging
import os

from flask import Flask, jsonify, request

from video_resolver import VideoResolver, extract_url_from_text, resolve_short_url, extract_aweme_id
from models import VideoRecord

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

app = Flask(__name__)
resolver = VideoResolver(timeout=15.0)

HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>抖音视频解析</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0f0f0f;
    color: #e0e0e0;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .container {
    width: 100%;
    max-width: 640px;
    padding: 24px;
  }
  h1 {
    text-align: center;
    font-size: 24px;
    font-weight: 600;
    margin-bottom: 8px;
    color: #fff;
  }
  .subtitle {
    text-align: center;
    font-size: 14px;
    color: #888;
    margin-bottom: 32px;
  }
  textarea {
    width: 100%;
    height: 120px;
    padding: 14px;
    border: 1px solid #333;
    border-radius: 10px;
    background: #1a1a1a;
    color: #e0e0e0;
    font-size: 15px;
    resize: vertical;
    outline: none;
    transition: border-color 0.2s;
  }
  textarea:focus { border-color: #fe2c55; }
  textarea::placeholder { color: #555; }
  .btn {
    width: 100%;
    padding: 14px;
    margin-top: 16px;
    border: none;
    border-radius: 10px;
    background: #fe2c55;
    color: #fff;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.2s;
  }
  .btn:hover { opacity: 0.9; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .result {
    margin-top: 24px;
    padding: 18px;
    border-radius: 10px;
    background: #1a1a1a;
    border: 1px solid #333;
    display: none;
    word-break: break-all;
  }
  .result.show { display: block; }
  .result.error { border-color: #ff4757; }
  .result.success { border-color: #2ed573; }
  .result-label {
    font-size: 12px;
    color: #888;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .result-row { margin-bottom: 14px; }
  .result-row:last-child { margin-bottom: 0; }
  .result-value { font-size: 14px; color: #e0e0e0; line-height: 1.5; }
  .result-url { display: flex; align-items: center; gap: 8px; }
  .result-url a { color: #fe2c55; text-decoration: none; flex: 1; word-break: break-all; }
  .result-url a:hover { text-decoration: underline; }
  .copy-btn {
    padding: 6px 12px;
    border: 1px solid #444;
    border-radius: 6px;
    background: transparent;
    color: #aaa;
    font-size: 12px;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s;
  }
  .copy-btn:hover { border-color: #fe2c55; color: #fe2c55; }
  .copy-btn.copied { border-color: #2ed573; color: #2ed573; }
  .error-msg { color: #ff4757; font-size: 14px; }
  .spinner {
    display: inline-block; width: 16px; height: 16px;
    border: 2px solid #fff; border-top-color: transparent;
    border-radius: 50%; animation: spin 0.6s linear infinite;
    vertical-align: middle; margin-right: 8px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="container">
  <h1>🎬 抖音视频解析</h1>
  <p class="subtitle">粘贴分享文本、短链接或视频链接，解析无水印下载地址</p>
  <textarea id="input" placeholder="粘贴抖音分享文本或链接&#10;&#10;例如：3.05 复制打开抖音，看看【xxx的作品】... https://v.douyin.com/xxx/"></textarea>
  <button class="btn" id="parseBtn" onclick="parse()">解析视频</button>
  <div class="result" id="result"></div>
</div>
<script>
async function parse() {
  const input = document.getElementById('input').value.trim();
  const btn = document.getElementById('parseBtn');
  const result = document.getElementById('result');
  if (!input) return;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>解析中...';
  result.className = 'result'; result.style.display = 'none';
  try {
    const resp = await fetch('/api/resolve', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({url: input})
    });
    const data = await resp.json();
    if (data.success) {
      result.className = 'result show success';
      result.innerHTML = `
        <div class="result-row"><div class="result-label">视频标题</div><div class="result-value">${esc(data.title||'未知')}</div></div>
        <div class="result-row"><div class="result-label">视频 ID</div><div class="result-value">${esc(data.aweme_id)}</div></div>
        <div class="result-row"><div class="result-label">视频时长</div><div class="result-value">${data.duration}s</div></div>
        <div class="result-row"><div class="result-label">下载地址</div>
          <div class="result-url"><a href="${esc(data.play_url)}" target="_blank">${esc(data.play_url)}</a>
          <button class="copy-btn" onclick="copyUrl(this,'${esc(data.play_url)}')">复制</button></div></div>`;
    } else {
      result.className = 'result show error';
      result.innerHTML = '<div class="error-msg">❌ '+esc(data.error)+'</div>';
    }
  } catch(e) {
    result.className = 'result show error';
    result.innerHTML = '<div class="error-msg">❌ 网络请求失败: '+esc(e.message)+'</div>';
  } finally { btn.disabled = false; btn.textContent = '解析视频'; }
}
function copyUrl(btn, url) {
  navigator.clipboard.writeText(url).then(()=>{
    btn.textContent='已复制'; btn.classList.add('copied');
    setTimeout(()=>{btn.textContent='复制';btn.classList.remove('copied');},2000);
  });
}
function esc(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML;}
document.getElementById('input').addEventListener('keydown',(e)=>{
  if((e.ctrlKey||e.metaKey)&&e.key==='Enter') parse();
});
</script>
</body>
</html>"""


@app.route("/")
def index():
    return HTML_PAGE


@app.route("/api/resolve", methods=["POST"])
def api_resolve():
    data = request.get_json(silent=True) or {}
    raw_input = data.get("url", "").strip()
    if not raw_input:
        return jsonify({"success": False, "error": "请输入链接或分享文本"})
    video = VideoRecord(title="", url=raw_input)
    result = resolver.resolve(video)
    if result.video_play_url:
        return jsonify({
            "success": True,
            "aweme_id": result.aweme_id,
            "play_url": result.video_play_url,
            "duration": round(result.duration_seconds, 1),
            "title": result.title or "",
        })
    else:
        return jsonify({"success": False, "error": "解析失败，请检查链接是否有效"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"\n🎬 抖音视频解析服务已启动")
    print(f"   访问地址: http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
