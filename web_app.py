"""抖音视频解析 Web 服务

轻量 Flask 应用，提供网页界面和 API 接口。
输入分享文本/短链接/长链接，解析出无水印下载地址。
可选：调用火山引擎接口将视频语音转为文字。

启动方式: python web_app.py
访问: http://localhost:8080
"""

import logging
import os

import requests
from flask import Flask, jsonify, request, Response

from video_resolver import VideoResolver, extract_url_from_text, resolve_short_url, extract_aweme_id
from models import VideoRecord
from config import Config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

app = Flask(__name__)
resolver = VideoResolver(timeout=15.0)

# 按需初始化转写器
_transcriber = None

def get_transcriber():
    global _transcriber
    if _transcriber is None and Config.is_transcribe_enabled():
        from transcriber import Transcriber
        _transcriber = Transcriber(
            app_id=Config.VOLC_APP_ID,
            access_token=Config.VOLC_ACCESS_TOKEN,
        )
    return _transcriber

# 按需初始化飞书客户端
_feishu_client = None

def get_feishu_client():
    global _feishu_client
    if _feishu_client is None and Config.is_feishu_enabled():
        from feishu_client import FeishuClient
        _feishu_client = FeishuClient(
            app_id=Config.FEISHU_APP_ID,
            app_secret=Config.FEISHU_APP_SECRET,
            folder_token=Config.FEISHU_FOLDER_TOKEN,
        )
    return _feishu_client

# 按需初始化 AI 处理器
_ai_processor = None

def get_ai_processor():
    global _ai_processor
    if _ai_processor is None and Config.is_ai_enabled():
        from ai_processor import AIProcessor
        _ai_processor = AIProcessor(
            api_key=Config.ARK_API_KEY,
            model=Config.ARK_MODEL,
        )
    return _ai_processor


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
  .btn-secondary {
    background: #2d2d2d;
    border: 1px solid #444;
    margin-top: 12px;
  }
  .btn-secondary:hover { border-color: #fe2c55; }
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
  .transcript-box {
    margin-top: 16px;
    padding: 16px;
    border-radius: 10px;
    background: #111;
    border: 1px solid #333;
    display: none;
  }
  .transcript-box.show { display: block; }
  .transcript-text {
    font-size: 14px;
    line-height: 1.8;
    color: #ccc;
    white-space: pre-wrap;
    max-height: 400px;
    overflow-y: auto;
  }
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
  <div class="transcript-box" id="transcriptBox">
    <div class="result-label">语音转文字</div>
    <div class="transcript-text" id="transcriptText"></div>
    <button class="copy-btn" style="margin-top:10px" onclick="copyTranscript()">复制文字</button>
  </div>
</div>
<script>
let lastPlayUrl = '';
let lastTitle = '';
let lastDuration = 0;
let lastSourceUrl = '';
let transcribeEnabled = TRANSCRIBE_ENABLED;
let feishuEnabled = FEISHU_ENABLED;

async function parse() {
  const input = document.getElementById('input').value.trim();
  const btn = document.getElementById('parseBtn');
  const result = document.getElementById('result');
  const tBox = document.getElementById('transcriptBox');
  if (!input) return;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>解析中...';
  result.className = 'result'; result.style.removeProperty('display');
  tBox.className = 'transcript-box';
  lastPlayUrl = '';
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(()=>ctrl.abort(), 45000);
    const resp = await fetch('/api/resolve', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({url: input}), signal: ctrl.signal
    });
    clearTimeout(timer);
    const data = await resp.json();
    if (data.success) {
      lastPlayUrl = data.play_url;
      lastTitle = data.title || '未知';
      lastDuration = data.duration;
      lastSourceUrl = input;
      let transcribeBtn = '';
      if (transcribeEnabled) {
        transcribeBtn = '<div class="result-row"><button class="btn btn-secondary" id="transcribeBtn" onclick="transcribe()">🎤 语音转文字</button></div>';
      }
      result.className = 'result show success';
      result.innerHTML = `
        <div class="result-row"><div class="result-label">视频标题</div><div class="result-value">${esc(data.title||'未知')}</div></div>
        <div class="result-row"><div class="result-label">视频 ID</div><div class="result-value">${esc(data.aweme_id)}</div></div>
        <div class="result-row"><div class="result-label">视频时长</div><div class="result-value">${data.duration}s</div></div>
        <div class="result-row"><div class="result-label">下载地址</div>
          <div class="result-url"><a href="${esc(data.play_url)}" target="_blank">${esc(data.play_url)}</a>
          <button class="copy-btn" data-url="${esc(data.play_url)}">复制</button><button class="copy-btn" onclick="downloadVideo()">下载</button></div></div>
        ${transcribeBtn}`;
      result.querySelector('.copy-btn').addEventListener('click', function(){copyUrl(this);});
    } else {
      result.className = 'result show error';
      result.innerHTML = '<div class="error-msg">❌ '+esc(data.error)+'</div>';
    }
  } catch(e) {
    result.className = 'result show error';
    const msg = e.name==='AbortError' ? '请求超时，请重试' : '网络请求失败: '+e.message;
    result.innerHTML = '<div class="error-msg">❌ '+esc(msg)+'</div>';
  } finally { btn.disabled = false; btn.textContent = '解析视频'; }
}

async function transcribe() {
  if (!lastPlayUrl) return;
  const btn = document.getElementById('transcribeBtn');
  const tBox = document.getElementById('transcriptBox');
  const tText = document.getElementById('transcriptText');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>转写中，请稍候...';
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(()=>ctrl.abort(), 180000);
    const resp = await fetch('/api/transcribe', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({url: lastPlayUrl}), signal: ctrl.signal
    });
    clearTimeout(timer);
    const data = await resp.json();
    if (data.success) {
      tText.textContent = data.text;
      tBox.className = 'transcript-box show';
      btn.textContent = '✅ 转写完成';
      btn.disabled = true;
      if (feishuEnabled) {
        let saveBtn = document.getElementById('saveFeishuBtn');
        if (!saveBtn) {
          saveBtn = document.createElement('button');
          saveBtn.id = 'saveFeishuBtn';
          saveBtn.className = 'btn btn-secondary';
          saveBtn.style.marginTop = '10px';
          saveBtn.textContent = '📝 AI润色并存入飞书';
          saveBtn.onclick = saveToFeishu;
          tBox.appendChild(saveBtn);
        }
        saveBtn.style.display = 'block';
        saveBtn.disabled = false;
        saveBtn.textContent = '📝 AI润色并存入飞书';
      }
    } else {
      btn.textContent = '❌ 转写失败';
      btn.disabled = false;
      alert('转写失败: ' + data.error);
    }
  } catch(e) {
    const msg = e.name==='AbortError' ? '转写超时' : '请求失败: '+e.message;
    btn.textContent = '🎤 语音转文字';
    btn.disabled = false;
    alert(msg);
  }
}

function copyUrl(btn) {
  const url = btn.getAttribute('data-url');
  const ta = document.createElement('textarea');
  ta.value = url; ta.style.position = 'fixed'; ta.style.opacity = '0';
  document.body.appendChild(ta); ta.select();
  try { document.execCommand('copy');
    btn.textContent='已复制'; btn.classList.add('copied');
    setTimeout(()=>{btn.textContent='复制';btn.classList.remove('copied');},2000);
  } catch(e) { alert('复制失败，请手动复制链接'); }
  document.body.removeChild(ta);
}

function copyTranscript() {
  const text = document.getElementById('transcriptText').textContent;
  const ta = document.createElement('textarea');
  ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
  document.body.appendChild(ta); ta.select();
  try { document.execCommand('copy');
    const btn = document.querySelector('#transcriptBox .copy-btn');
    btn.textContent='已复制'; btn.classList.add('copied');
    setTimeout(()=>{btn.textContent='复制文字';btn.classList.remove('copied');},2000);
  } catch(e) { alert('复制失败'); }
  document.body.removeChild(ta);
}

function downloadVideo() {
  if (!lastPlayUrl) return;
  window.open('/api/download?url=' + encodeURIComponent(lastPlayUrl) + '&title=' + encodeURIComponent(lastTitle), '_blank');
}

async function saveToFeishu() {
  const btn = document.getElementById('saveFeishuBtn');
  const text = document.getElementById('transcriptText').textContent;
  if (!text) return;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>AI处理+保存中...';
  try {
    const resp = await fetch('/api/save_feishu', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({title: lastTitle, author: '', source_url: lastSourceUrl, duration: lastDuration, text: text}),
      signal: AbortSignal.timeout(90000)
    });
    const data = await resp.json();
    if (data.success) {
      btn.innerHTML = '✅ 已保存到飞书';
      btn.disabled = true;
      if (data.doc_url) {
        const link = document.createElement('a');
        link.href = data.doc_url; link.target = '_blank';
        link.textContent = '打开文档'; link.style.cssText = 'color:#fe2c55;margin-left:12px;font-size:14px;';
        btn.parentNode.insertBefore(link, btn.nextSibling);
      }
    } else {
      btn.textContent = '❌ 保存失败'; btn.disabled = false;
      alert('保存失败: ' + data.error);
    }
  } catch(e) {
    btn.textContent = '📝 AI润色并存入飞书'; btn.disabled = false;
    alert('请求失败: ' + e.message);
  }
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
    # 动态注入功能开关到前端
    enabled = "true" if Config.is_transcribe_enabled() else "false"
    feishu = "true" if Config.is_feishu_enabled() else "false"
    page = HTML_PAGE.replace("TRANSCRIBE_ENABLED", enabled).replace("FEISHU_ENABLED", feishu)
    return page


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


@app.route("/api/transcribe", methods=["POST"])
def api_transcribe():
    """语音转文字接口"""
    transcriber = get_transcriber()
    if not transcriber:
        return jsonify({"success": False, "error": "转写功能未配置，请设置 VOLC_APP_ID 和 VOLC_ACCESS_TOKEN"})

    data = request.get_json(silent=True) or {}
    audio_url = data.get("url", "").strip()
    if not audio_url:
        return jsonify({"success": False, "error": "请提供音频 URL"})

    result = transcriber.transcribe(audio_url)
    if result.error:
        return jsonify({"success": False, "error": result.error})

    return jsonify({
        "success": True,
        "text": result.text,
        "duration": round(result.duration, 1),
        "utterance_count": len(result.utterances),
    })


@app.route("/api/download")
def api_download():
    """代理下载视频（绕过抖音 Referer 防盗链）"""
    video_url = request.args.get("url", "").strip()
    title = request.args.get("title", "video").strip() or "video"
    if not video_url:
        return jsonify({"success": False, "error": "缺少 url 参数"}), 400

    import re
    safe_title = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', title)[:60]

    try:
        headers = {
            "user-agent": "Mozilla/5.0 (Linux; Android 8.0.0) AppleWebKit/537.36 Chrome/116.0.0.0 Mobile Safari/537.36",
            "referer": "https://www.douyin.com/",
        }
        upstream = requests.get(video_url, headers=headers, stream=True, timeout=30, allow_redirects=True)
        if upstream.status_code != 200:
            return jsonify({"success": False, "error": f"上游返回 {upstream.status_code}"}), 502

        content_type = upstream.headers.get("Content-Type", "video/mp4")
        content_length = upstream.headers.get("Content-Length", "")

        resp_headers = {
            "Content-Type": content_type,
            "Content-Disposition": f'attachment; filename="{safe_title}.mp4"',
        }
        if content_length:
            resp_headers["Content-Length"] = content_length

        return Response(upstream.iter_content(chunk_size=65536), headers=resp_headers)
    except requests.RequestException as e:
        return jsonify({"success": False, "error": str(e)}), 502


@app.route("/api/save_feishu", methods=["POST"])
def api_save_feishu():
    """保存转写文字到飞书文档（含 AI 纠错+摘要）"""
    client = get_feishu_client()
    if not client:
        return jsonify({"success": False, "error": "飞书功能未配置"})

    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"success": False, "error": "没有可保存的文字内容"})

    # AI 处理：纠错 + 摘要
    final_text = text
    summary = ""
    ai = get_ai_processor()
    if ai:
        ai_result = ai.process(text)
        if ai_result.success:
            final_text = ai_result.corrected_text
            summary = ai_result.summary
        else:
            logging.warning(f"AI 处理失败，使用原始文字: {ai_result.error}")

    result = client.save_transcript(
        title=data.get("title", "未知视频"),
        author=data.get("author", ""),
        source_url=data.get("source_url", ""),
        duration=data.get("duration", 0),
        text=final_text,
        summary=summary,
    )

    if result.success:
        return jsonify({"success": True, "doc_url": result.doc_url, "doc_title": result.doc_title})
    else:
        return jsonify({"success": False, "error": result.error})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"\n🎬 抖音视频解析服务已启动")
    print(f"   访问地址: http://localhost:{port}")
    if Config.is_transcribe_enabled():
        print(f"   ✅ 语音转文字: 已启用")
    else:
        print(f"   ⚠️  语音转文字: 未配置 (设置 VOLC_APP_ID + VOLC_ACCESS_TOKEN 启用)")
    if Config.is_feishu_enabled():
        print(f"   ✅ 飞书知识库: 已启用")
    else:
        print(f"   ⚠️  飞书知识库: 未配置 (设置 FEISHU_APP_ID + FEISHU_APP_SECRET + FEISHU_FOLDER_TOKEN 启用)")
    if Config.is_ai_enabled():
        print(f"   ✅ AI 润色: 已启用 (模型: {Config.ARK_MODEL})")
    else:
        print(f"   ⚠️  AI 润色: 未配置 (设置 ARK_API_KEY 启用)")
    print()
    app.run(host="0.0.0.0", port=port, debug=False)
