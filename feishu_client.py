"""飞书文档客户端

通过飞书开放平台 API，在指定文件夹下创建文档并写入内容。
用于将视频转写文字稿存入飞书知识库。

需要配置：
- FEISHU_APP_ID: 飞书应用 App ID
- FEISHU_APP_SECRET: 飞书应用 App Secret
- FEISHU_FOLDER_TOKEN: 目标文件夹 token
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_BASE = "https://open.feishu.cn/open-apis"


@dataclass
class FeishuDocResult:
    """创建文档的结果"""
    success: bool
    doc_url: str = ""
    doc_title: str = ""
    error: Optional[str] = None


class FeishuClient:
    """飞书文档客户端"""

    def __init__(self, app_id: str, app_secret: str, folder_token: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.folder_token = folder_token
        self._token: Optional[str] = None
        self._token_expires: float = 0

    def _get_token(self) -> str:
        """获取 tenant_access_token（带缓存）"""
        if self._token and time.time() < self._token_expires:
            return self._token

        resp = requests.post(f"{_BASE}/auth/v3/tenant_access_token/internal", json={
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }, timeout=10)

        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取飞书 token 失败: {data.get('msg')}")

        self._token = data["tenant_access_token"]
        self._token_expires = time.time() + data.get("expire", 7200) - 300
        return self._token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    def save_transcript(
        self,
        title: str,
        author: str,
        source_url: str,
        duration: float,
        text: str,
    ) -> FeishuDocResult:
        """将转写文字稿保存为飞书文档

        Args:
            title: 视频标题
            author: 作者/博主名
            source_url: 视频来源链接
            duration: 视频时长（秒）
            text: 转写文字内容
        """
        now = time.strftime("%Y-%m-%d %H:%M")
        doc_title = f"[{now[:10]}] {title} - {author}" if author else f"[{now[:10]}] {title}"

        try:
            # 1. 创建文档
            doc_resp = requests.post(
                f"{_BASE}/docx/v1/documents",
                headers=self._headers(),
                json={"folder_token": self.folder_token, "title": doc_title},
                timeout=15,
            )
            doc_data = doc_resp.json()
            if doc_data.get("code") != 0:
                msg = doc_data.get("msg", "未知错误")
                logger.error(f"创建文档失败: {msg}")
                return FeishuDocResult(success=False, error=f"创建文档失败: {msg}")

            document = doc_data["data"]["document"]
            doc_id = document["document_id"]
            doc_url = f"https://my.feishu.cn/docx/{doc_id}"

            # 2. 获取文档根 block ID
            block_resp = requests.get(
                f"{_BASE}/docx/v1/documents/{doc_id}/blocks/{doc_id}",
                headers=self._headers(),
                timeout=10,
            )
            # 根 block 的 children 里第一个是默认的空段落，我们往根 block 下追加内容

            # 3. 写入元信息 + 正文
            blocks = self._build_blocks(title, author, now, source_url, duration, text)

            create_resp = requests.post(
                f"{_BASE}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                headers=self._headers(),
                json={"children": blocks, "index": 0},
                timeout=30,
            )
            create_data = create_resp.json()
            if create_data.get("code") != 0:
                msg = create_data.get("msg", "未知错误")
                logger.error(f"写入文档内容失败: {msg}")
                return FeishuDocResult(success=False, doc_url=doc_url, error=f"写入内容失败: {msg}")

            logger.info(f"文档已保存: {doc_title} -> {doc_url}")
            return FeishuDocResult(success=True, doc_url=doc_url, doc_title=doc_title)

        except requests.RequestException as e:
            logger.error(f"飞书 API 请求失败: {e}")
            return FeishuDocResult(success=False, error=f"网络请求失败: {e}")

    @staticmethod
    def _build_blocks(title, author, time_str, source_url, duration, text):
        """构建飞书文档 block 列表"""

        def text_block(content: str) -> dict:
            """创建文本段落 block"""
            return {
                "block_type": 2,
                "text": {
                    "elements": [{"text_run": {"content": content}}],
                    "style": {},
                },
            }

        def divider_block() -> dict:
            return {"block_type": 22, "divider": {}}

        blocks = []

        # 元信息区域
        meta_lines = [
            f"作者：{author}" if author else "作者：未知",
            f"时间：{time_str}",
            f"来源：{source_url}",
            f"时长：{duration:.1f}s",
        ]
        for line in meta_lines:
            blocks.append(text_block(line))

        # 分割线
        blocks.append(divider_block())

        # 正文
        # 飞书单个 text_run 有长度限制，按段落拆分
        paragraphs = text.split("\n") if "\n" in text else [text]
        for p in paragraphs:
            if p.strip():
                blocks.append(text_block(p.strip()))

        return blocks
