import httpx
from utils.logger import logger


# ==========================================
# 外部技能：获取实时天气
# ==========================================
async def get_realtime_weather(city_name: str) -> str:
    """
    智能体外部工具：查天气
    作用：大模型本身无法知道“今天”的天气，通过这个工具，向外部气象服务器发请求获取实时数据。

    :param city_name: 城市名称，比如 "苏州"、"Shanghai" (大模型会自动从用户话语中提取)
    :return: 拼装好的大白话天气信息，直接喂给大模型做参考
    """
    logger.info(f"🌤️ [Weather Tool] 大模型正在调用天气技能，查询城市: {city_name}")

    # 1. 确定我们要请求的 API 地址
    # wttr.in 是一个极客常用的免费天气 API，?format=j1 表示让它返回 JSON 格式数据
    url = f"https://wttr.in/{city_name}?format=j1"

    try:
        # 2. 🚨 核心异步网络请求 (面试常考点)
        # 使用 httpx.AsyncClient 代替传统的 requests，确保在等天气返回的这几百毫秒内，
        # 我们的 FastAPI 服务器还可以去处理其他用户的聊天请求，绝对不阻塞主线程！
        # timeout=5.0 表示如果外部服务器 5 秒不理我，就直接报错，防止系统被拖死。
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)

            # 3. 检查 HTTP 状态码，如果不是 200 (成功)，则抛出异常跳入 except 块
            response.raise_for_status()

            # 4. 将返回的二进制/文本数据，解析成 Python 的字典 (JSON)
            data = response.json()

            # 5. 从极其复杂的 JSON 嵌套里，像剥洋葱一样提取我们需要的数据
            # (注意：这些 key 都是 API 厂商定死的，不用背，查文档就行)
            current_temp = data['current_condition'][0]['temp_C']  # 当前温度(摄氏度)
            feels_like = data['current_condition'][0]['FeelsLikeC']  # 体感温度
            humidity = data['current_condition'][0]['humidity']  # 湿度
            weather_desc = data['current_condition'][0]['lang_zh'][0]['value'] if 'lang_zh' in \
                                                                                  data['current_condition'][0] else \
            data['current_condition'][0]['weatherDesc'][0]['value']

            # 6. 🚨 极其重要的数据翻译 (Tool 的灵魂)
            # 大模型不喜欢看 {"temp": 25, "desc": "Sunny"} 这样的字典。
            # 我们必须用大白话把它拼起来，这样大模型阅读参考资料时才不会“脑雾”。
            weather_report = (
                f"【实时天气情报】城市：{city_name}，"
                f"当前天气情况：{weather_desc}，"
                f"实际温度：{current_temp}℃，体感温度：{feels_like}℃，"
                f"空气湿度：{humidity}%。"
            )

            logger.info(f"✅ [Weather Tool] 成功获取天气数据: {weather_report}")
            return weather_report

    except httpx.TimeoutException:
        logger.warning(f"⚠️ [Weather Tool] 请求天气 API 超时 (城市: {city_name})。")
        return f"抱歉，查询 {city_name} 天气的服务超时了，请稍后再试。"

    except Exception as e:
        logger.error(f"❌ [Weather Tool] 获取天气失败: {e}")
        return "外部天气服务暂时不可用，请告知用户系统网络异常。"