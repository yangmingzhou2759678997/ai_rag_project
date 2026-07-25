import json
import unittest

import httpx
from openai import RateLimitError
from starlette.requests import Request

from utils.exception_handlers import global_exception_handler, upstream_rate_limit_exception_handler


class ExceptionHandlerTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.request = Request({"type": "http", "method": "POST", "path": "/api/chat/completions", "headers": []})

    async def test_upstream_rate_limit_returns_503(self):
        """上游模型限流应返回安全的503响应。"""
        upstream_request = httpx.Request("POST", "https://example.com/chat")
        upstream_response = httpx.Response(429, request=upstream_request)
        exception = RateLimitError("rate limit", response=upstream_response, body={"code": 50609})

        response = await upstream_rate_limit_exception_handler(self.request, exception)
        content = json.loads(response.body)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(content["code"], 503)
        self.assertEqual(content["msg"], "大模型服务繁忙，请稍后再试")
        self.assertIsNone(content["data"])

    async def test_global_handler_accepts_braces_in_exception(self):
        """包含大括号的异常文本不应再次触发日志格式化错误。"""
        exception = Exception("Error code: 429 - {'code': 50609}")

        response = await global_exception_handler(self.request, exception)
        content = json.loads(response.body)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(content, {"code": 500, "msg": "服务器开小差了，请稍后再试", "data": None})


if __name__ == "__main__":
    unittest.main()
