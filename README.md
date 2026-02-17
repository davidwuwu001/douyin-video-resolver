# 抖音视频解析器

粘贴抖音分享文本、短链接或视频链接，一键解析无水印下载地址。
可选：调用火山引擎接口将视频语音转为文字。

## 快速启动

```bash
pip install -r requirements.txt
python web_app.py
```

访问 http://localhost:8080

## 服务器部署（gunicorn）

```bash
pip install -r requirements.txt

# 基础功能（仅视频解析）
gunicorn -w 2 -b 0.0.0.0:3101 --timeout 60 web_app:app

# 启用语音转文字（需配置环境变量）
export VOLC_APP_ID=your_app_id
export VOLC_ACCESS_TOKEN=your_token
gunicorn -w 2 -b 0.0.0.0:3101 --timeout 120 web_app:app
```

## 语音转文字配置

使用火山引擎「豆包语音 - 音视频字幕生成」接口，需要：

1. 注册火山引擎: https://console.volcengine.com/
2. 开通「豆包语音」→ 创建应用 → 获取 App ID
3. 生成 Access Token
4. 开通「音视频字幕生成」能力

详见 `.env.example` 文件。

## 支持的输入格式

- 标准长链接：`https://www.douyin.com/video/xxx`
- 短链接：`https://v.douyin.com/xxx`
- 分享文本：`3.05 复制打开抖音... https://v.douyin.com/xxx/ ...`

## API 接口

- `POST /api/resolve` - 解析视频下载地址
- `POST /api/transcribe` - 语音转文字（需配置火山引擎）
