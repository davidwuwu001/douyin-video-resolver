# 抖音视频解析器

粘贴抖音分享文本、短链接或视频链接，一键解析无水印下载地址。

## 快速启动

```bash
pip install -r requirements.txt
python web_app.py
```

访问 http://localhost:8080

## 服务器部署（gunicorn）

```bash
pip install -r requirements.txt
gunicorn -w 4 -b 0.0.0.0:8080 web_app:app
```

## 支持的输入格式

- 标准长链接：`https://www.douyin.com/video/xxx`
- 短链接：`https://v.douyin.com/xxx`
- 分享文本：`3.05 复制打开抖音... https://v.douyin.com/xxx/ ...`
