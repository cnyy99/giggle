import asyncio
import aiohttp
import openai
from typing import Dict, List
from utils.logger import setup_logger

logger = setup_logger(__name__)


class TranslationService:
    """翻译服务 - 支持多种翻译引擎"""

    def __init__(self, config):
        self.config = config
        self.openai_client = None
        self.session = None

        # 语言代码映射
        self.language_mapping = {
            'en': 'English',
            'zh-cn': 'Simplified Chinese',
            'zh-tw': 'Traditional Chinese',
            'ja': 'Japanese',
            'ko': 'Korean',
            'fr': 'French',
            'de': 'German',
            'es': 'Spanish',
            'ru': 'Russian',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ar': 'Arabic'
        }

    async def _get_session(self):
        """获取HTTP会话"""
        """获取HTTP会话"""
        if self.session is None:
            # 设置连接和读取超时
            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def translate_text(self, text: str, source_lang: str,
                             target_languages: List[str], task_id: str = None,
                             cancelled_tasks_set: set = None) -> Dict[str, str]:
        """翻译文本到多种语言"""
        translations = {}

        logger.info(f"start translate text: {text} to {target_languages}")
        # 检查取消状态
        if cancelled_tasks_set and task_id and task_id in cancelled_tasks_set:
            logger.warning(f"Cancelled: {task_id}")
            raise asyncio.CancelledError(f"Task {task_id} was cancelled")

        # 并发翻译到所有目标语言
        tasks = []
        for target_lang in target_languages:
            if target_lang != source_lang:
                task = self._translate_single_with_cancellation(
                    text, source_lang, target_lang, task_id, cancelled_tasks_set
                )
                tasks.append((target_lang, task))

        # 等待所有翻译完成，支持取消
        try:
            results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        except asyncio.CancelledError:
            # 如果任务被取消，立即返回
            logger.info(f"Translation task {task_id} was cancelled")
            raise

        # 处理结果前再次检查取消状态
        if cancelled_tasks_set and task_id and task_id in cancelled_tasks_set:
            raise asyncio.CancelledError(f"Task {task_id} was cancelled")

        # 处理结果
        for i, (target_lang, _) in enumerate(tasks):
            result = results[i]
            if isinstance(result, Exception):
                if isinstance(result, asyncio.CancelledError):
                    raise result
                logger.error(f"Translation to {target_lang} failed: {result}")
                translations[target_lang] = f"[Translation Error: {str(result)}]"
            else:
                translations[target_lang] = result

        # 添加原文
        translations[source_lang] = text
        return translations

    async def _translate_single_with_cancellation(self, text: str, source_lang: str,
                                                  target_lang: str, task_id: str = None,
                                                  cancelled_tasks_set: set = None) -> str:
        logger.info(f"start translate text: {text} to {target_lang}")

        """单个语言翻译，支持取消检查"""
        # 在翻译开始前检查取消状态
        if cancelled_tasks_set and task_id and task_id in cancelled_tasks_set:
            raise asyncio.CancelledError(f"Task {task_id} was cancelled")

        return await self._translate_single(text, source_lang, target_lang)

    async def _translate_single(self, text: str, source_lang: str, target_lang: str) -> str:
        """单个语言翻译"""
        try:
            # 1. 优先使用OpenAI GPT进行翻译
            if self.config.TRANSLATION_API_KEY:
                return await self._translate_with_openai(text, source_lang, target_lang)

            # 2. 备用：使用Google翻译
            if hasattr(self.config, 'GOOGLE_TRANSLATE_API_KEY') and self.config.GOOGLE_TRANSLATE_API_KEY:
                try:
                    return await self._translate_with_google(text, source_lang, target_lang)
                except Exception as google_error:
                    logger.warning(f"Google translation failed, trying DeepL: {google_error}")

            # 3. 备用：使用DeepL翻译
            if hasattr(self.config, 'DEEPL_API_KEY') and self.config.DEEPL_API_KEY:
                try:
                    return await self._translate_with_deepl(text, source_lang, target_lang)
                except Exception as deepl_error:
                    logger.warning(f"DeepL translation failed, trying LibreTranslate: {deepl_error}")

            # 4. 最后备用：使用免费翻译API
            return await self._translate_with_libre(text, source_lang, target_lang)

        except Exception as e:
            logger.error(f"Translation failed for {source_lang} -> {target_lang}: {e}")
            raise

    async def _translate_with_google(self, text: str, source_lang: str, target_lang: str) -> str:
        """使用Google翻译API进行翻译"""
        try:
            session = await self._get_session()

            # Google Cloud Translation API v2
            url = "https://translation.googleapis.com/language/translate/v2"

            # 语言代码转换
            google_source = self._convert_to_google_code(source_lang)
            google_target = self._convert_to_google_code(target_lang)

            params = {
                "key": self.config.GOOGLE_TRANSLATE_API_KEY,
                "q": text,
                "source": google_source,
                "target": google_target,
                "format": "text"
            }

            async with session.post(url, params=params) as response:
                if response.status == 200:
                    result = await response.json()
                    translation = result["data"]["translations"][0]["translatedText"]
                    logger.info(f"Google translation completed: {source_lang} -> {target_lang}")
                    return translation
                else:
                    error_text = await response.text()
                    raise Exception(f"Google Translate API error: {response.status} - {error_text}")

        except Exception as e:
            logger.error(f"Google translation failed: {e}")
            raise

    async def _translate_with_bing(self, text: str, source_lang: str, target_lang: str) -> str:
        """使用Bing翻译API进行翻译"""
        try:
            session = await self._get_session()

            # Microsoft Translator Text API v3.0
            url = "https://api.cognitive.microsofttranslator.com/translate"

            # 语言代码转换
            bing_source = self._convert_to_bing_code(source_lang)
            bing_target = self._convert_to_bing_code(target_lang)

            headers = {
                "Ocp-Apim-Subscription-Key": self.config.BING_TRANSLATE_API_KEY,
                "Ocp-Apim-Subscription-Region": getattr(self.config, 'BING_TRANSLATE_REGION', 'global'),
                "Content-Type": "application/json"
            }

            params = {
                "api-version": "3.0",
                "from": bing_source,
                "to": bing_target
            }

            body = [{"text": text}]

            async with session.post(url, headers=headers, params=params, json=body) as response:
                if response.status == 200:
                    result = await response.json()
                    translation = result[0]["translations"][0]["text"]
                    logger.info(f"Bing translation completed: {source_lang} -> {target_lang}")
                    return translation
                else:
                    error_text = await response.text()
                    raise Exception(f"Bing Translate API error: {response.status} - {error_text}")

        except Exception as e:
            logger.error(f"Bing translation failed: {e}")
            raise

    def _convert_to_google_code(self, lang_code: str) -> str:
        """转换语言代码为Google翻译格式"""
        mapping = {
            'zh-cn': 'zh-cn',
            'zh-tw': 'zh-tw',
            'ja': 'ja',
            'ko': 'ko',
            'en': 'en',
            'fr': 'fr',
            'de': 'de',
            'es': 'es',
            'ru': 'ru',
            'it': 'it',
            'pt': 'pt',
            'ar': 'ar',
            'hi': 'hi',
            'th': 'th',
            'vi': 'vi',
            'tr': 'tr',
            'pl': 'pl',
            'nl': 'nl',
            'sv': 'sv',
            'da': 'da',
            'no': 'no',
            'fi': 'fi'
        }
        return mapping.get(lang_code, 'en')

    def _convert_to_bing_code(self, lang_code: str) -> str:
        """转换语言代码为Bing翻译格式"""
        mapping = {
            'zh-cn': 'zh-Hans',
            'zh-tw': 'zh-Hant',
            'ja': 'ja',
            'ko': 'ko',
            'en': 'en',
            'fr': 'fr',
            'de': 'de',
            'es': 'es',
            'ru': 'ru',
            'it': 'it',
            'pt': 'pt',
            'ar': 'ar',
            'hi': 'hi',
            'th': 'th',
            'vi': 'vi',
            'tr': 'tr',
            'pl': 'pl',
            'nl': 'nl',
            'sv': 'sv',
            'da': 'da',
            'nb': 'nb',  # 挪威语
            'fi': 'fi'
        }
        return mapping.get(lang_code, 'en')

    async def _translate_with_openai(self, text: str, source_lang: str, target_lang: str) -> str:
        """使用OpenAI GPT进行翻译"""
        try:
            if self.openai_client is None:
                openai.api_key = self.config.TRANSLATION_API_KEY
                self.openai_client = openai.AsyncOpenAI(api_key=self.config.TRANSLATION_API_KEY)

            source_name = self.language_mapping.get(source_lang, source_lang)
            target_name = self.language_mapping.get(target_lang, target_lang)

            prompt = f"""Translate the following text from {source_name} to {target_name}. 
Provide only the translation without any additional text or explanation.

Text to translate:
{text}"""

            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system",
                     "content": "You are a professional translator. Provide accurate and natural translations."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3
            )

            translation = response.choices[0].message.content.strip()
            logger.info(f"OpenAI translation completed: {source_lang} -> {target_lang}")
            return translation

        except Exception as e:
            logger.error(f"OpenAI translation failed: {e}")
            raise

    async def _translate_with_libre(self, text: str, source_lang: str, target_lang: str) -> str:
        """使用LibreTranslate进行翻译"""
        try:
            session = await self._get_session()

            # LibreTranslate API
            url = "https://libretranslate.de/translate"

            # 语言代码转换
            libre_source = self._convert_to_libre_code(source_lang)
            libre_target = self._convert_to_libre_code(target_lang)

            data = {
                "q": text,
                "source": libre_source,
                "target": libre_target,
                "format": "text"
            }

            async with session.post(url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    translation = result.get("translatedText", "")
                    logger.info(f"LibreTranslate translation completed: {source_lang} -> {target_lang}")
                    return translation
                else:
                    error_text = await response.text()
                    raise Exception(f"LibreTranslate API error: {response.status} - {error_text}")

        except Exception as e:
            logger.error(f"LibreTranslate translation failed: {e}")
            # 备用：使用本地翻译字典
            return await self._translate_with_dict(text, source_lang, target_lang)

    def _convert_to_libre_code(self, lang_code: str) -> str:
        """转换语言代码为LibreTranslate格式"""
        mapping = {
            'zh-cn': 'zh',
            'zh-tw': 'zh',
            'ja': 'ja',
            'ko': 'ko',
            'en': 'en',
            'fr': 'fr',
            'de': 'de',
            'es': 'es',
            'ru': 'ru',
            'it': 'it',
            'pt': 'pt',
            'ar': 'ar'
        }
        return mapping.get(lang_code, 'en')

    async def _translate_with_dict(self, text: str, source_lang: str, target_lang: str) -> str:
        """使用本地翻译字典（备用方案）"""
        # 这里可以实现一个简单的词典翻译
        # 或者调用其他翻译服务
        logger.warning(f"Using fallback translation for {source_lang} -> {target_lang}")
        return f"[todo use another translator][Translated from {source_lang} to {target_lang}]: {text}"

    async def detect_language(self, text: str) -> str:
        """检测文本语言"""
        try:
            # 使用简单的语言检测逻辑
            # 实际项目中可以使用langdetect或其他库
            import re

            # 检测中文
            if re.search(r'[\u4e00-\u9fff]', text):
                # 进一步区分简繁体
                simplified_chars = set(
                    '的了在是我有个这你们来到时大地为上就一去道出而要会年生可以还人得之后自己回事好只那些知道就要这样')
                traditional_chars = set(
                    '的了在是我有個這你們來到時大地為上就一去道出而要會年生可以還人得之後自己回事好只那些知道就要這樣')

                simplified_count = sum(1 for char in text if char in simplified_chars)
                traditional_count = sum(1 for char in text if char in traditional_chars)

                return 'zh-cn' if simplified_count >= traditional_count else 'zh-tw'

            # 检测日文
            if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text):
                return 'ja'

            # 检测韩文
            if re.search(r'[\uac00-\ud7af]', text):
                return 'ko'

            # 检测阿拉伯文
            if re.search(r'[\u0600-\u06ff]', text):
                return 'ar'

            # 检测俄文
            if re.search(r'[\u0400-\u04ff]', text):
                return 'ru'

            # 默认英文
            return 'en'

        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            return 'en'

    async def cleanup(self):
        """清理资源"""
        if self.session:
            await self.session.close()

    async def _translate_with_deepl(self, text: str, source_lang: str, target_lang: str) -> str:
        """使用DeepL API进行翻译"""
        try:
            logger.info(f"Using deepl translation for {source_lang} -> {target_lang}")
            session = await self._get_session()

            # DeepL API v2
            url = f"{self.config.DEEPL_API_URL}/v2/translate"

            # 语言代码转换
            deepl_source = self._convert_to_deepl_code(source_lang)
            deepl_target = self._convert_to_deepl_code(target_lang)

            headers = {
                "Authorization": f"DeepL-Auth-Key {self.config.DEEPL_API_KEY}",
                "Content-Type": "application/x-www-form-urlencoded"
            }

            data = {
                "text": text,
                "source_lang": deepl_source,
                "target_lang": deepl_target
            }

            async with session.post(url, headers=headers, data=data,timeout=1) as response:
                if response.status == 200:
                    result = await response.json()
                    translation = result["translations"][0]["text"]
                    logger.info(
                        f"DeepL translation completed: {source_lang} -> {target_lang}, translation: {translation}, result: {result}")
                    return translation
                else:
                    error_text = await response.text()
                    raise Exception(f"DeepL API error: {response.status} - {error_text}")

        except Exception as e:
            logger.error(f"DeepL translation failed: {e}")
            raise

    def _convert_to_deepl_code(self, lang_code: str) -> str:
        """转换语言代码为DeepL格式"""
        mapping = {
            'zh-cn': 'ZH-HANS',  # 中文简体
            'zh-tw': 'ZH-HANT',  # 中文繁体
            'ja': 'JA',
            'ko': 'KO',
            'en': 'EN',  # 默认使用美式英语
            'en-gb': 'EN',  # 英式英语
            'en-us': 'EN',  # 美式英语
            'fr': 'FR',
            'de': 'DE',
            'es': 'ES',
            'ru': 'RU',
            'it': 'IT',
            'pt': 'PT',  # 默认使用欧洲葡萄牙语
            'pt-br': 'PT',  # 巴西葡萄牙语
            'pt-pt': 'PT',  # 欧洲葡萄牙语
            'ar': 'AR',  # 阿拉伯语
            'th': 'TH',  # 泰语
            'vi': 'VI',  # 越南语
            'tr': 'TR',  # 土耳其语
            'pl': 'PL',  # 波兰语
            'nl': 'NL',  # 荷兰语
            'sv': 'SV',  # 瑞典语
            'da': 'DA',  # 丹麦语
            'no': 'NB',  # 挪威语
            'fi': 'FI',  # 芬兰语
            'bg': 'BG',  # 保加利亚语
            'cs': 'CS',  # 捷克语
            'el': 'EL',  # 希腊语
            'et': 'ET',  # 爱沙尼亚语
            'he': 'HE',  # 希伯来语
            'hu': 'HU',  # 匈牙利语
            'id': 'ID',  # 印尼语
            'lt': 'LT',  # 立陶宛语
            'lv': 'LV',  # 拉脱维亚语
            'ro': 'RO',  # 罗马尼亚语
            'sk': 'SK',  # 斯洛伐克语
            'sl': 'SL',  # 斯洛文尼亚语
            'uk': 'UK',  # 乌克兰语
        }
        return mapping.get(lang_code, 'EN')
