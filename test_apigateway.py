import requests
import json
import time
import os
from pathlib import Path
from typing import Dict, List, Optional
import pytest


class TestAPIGateway:
    """API Gateway测试类 - 使用pytest框架"""

    @pytest.fixture(scope="class", autouse=True)
    @classmethod  # 添加classmethod装饰器
    def setup_class(cls):
        """类级别的设置"""
        cls.base_url = "http://localhost:8080"
        cls.api_base = f"{cls.base_url}/api/v1/translation"
        cls.node_api = f"{cls.base_url}/api"
        cls.session = requests.Session()
        cls.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

        # 测试资源路径
        cls.resource_path = Path("./resources")

        # 加载文本数据 - 在设置resource_path之后调用
        cls.text_data = cls._load_text_data()

        yield

        # 清理
        cls.session.close()

    @classmethod
    def _load_text_data(cls) -> Dict[str, str]:
        """加载text.json文件"""
        # 确保resource_path已经设置
        if not hasattr(cls, 'resource_path'):
            cls.resource_path = Path("./resources")

        text_file = cls.resource_path / "text.json"
        try:
            with open(text_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"警告: 加载text.json失败: {e}")
            # 返回默认测试数据
            return {
                "1": "Hello, this is a test message for translation.",
                "2": "Welcome to our translation service.",
                "3": "This is another test sentence."
            }

    def test_connection(self):
        """测试API Gateway连接"""
        try:
            response = self.session.get(f"{self.node_api}/nodes")
            print(f"✓ API Gateway连接测试: {response.status_code}")
            assert response.status_code == 200, f"连接失败，状态码: {response.status_code}"
        except Exception as e:
            pytest.fail(f"API Gateway连接失败: {e}")

    def test_get_nodes(self):
        """测试获取节点列表"""
        print("\n=== 测试获取节点列表 ===")
        try:
            response = self.session.get(f"{self.node_api}/nodes")
            print(f"状态码: {response.status_code}")

            assert response.status_code == 200, f"获取节点失败，状态码: {response.status_code}"

            nodes = response.json()
            print(f"节点数量: {len(nodes)}")
            for node in nodes:
                print(f"  - 节点信息: {node}")

            assert isinstance(nodes, list), "返回的节点数据应该是列表"

        except Exception as e:
            pytest.fail(f"获取节点异常: {e}")

    def test_get_available_nodes(self):
        """测试获取可用节点"""
        print("\n=== 测试获取可用节点 ===")
        try:
            response = self.session.get(f"{self.node_api}/nodes/available")
            print(f"状态码: {response.status_code}")

            assert response.status_code == 200, f"获取可用节点失败，状态码: {response.status_code}"

            nodes = response.json()
            print(f"可用节点数量: {len(nodes)}")
            for node in nodes:
                print(f"  - 节点信息: {node}")

            assert isinstance(nodes, list), "返回的可用节点数据应该是列表"

        except Exception as e:
            pytest.fail(f"获取可用节点异常: {e}")

    @pytest.mark.parametrize("text_id", ["1", "2", "3"])
    def test_create_text_task(self, text_id: str):
        """测试创建文本翻译任务"""
        print(f"\n=== 测试创建文本翻译任务 (文本ID: {text_id}) ===")

        # 从text.json获取对应的文本内容
        text_content = self.text_data.get(text_id, "Hello, this is a test message for translation.")

        task_data = {
            "sourceLanguage": "en",
            "targetLanguages": ['zh-cn', 'zh-tw', 'zh', 'en', 'en-us', 'en-gb', 'pt', 'pt-br', 'pt-pt', 'ar', 'bg',
                                'cs', 'da', 'de', 'el', 'es', 'et', 'fi', 'fr', 'he', 'hu', 'id', 'it', 'ja', 'ko',
                                'lt', 'lv', 'nb', 'no', 'nl', 'pl', 'ro', 'ru', 'sk', 'sl', 'sv', 'th', 'tr', 'uk',
                                'vi'],
            "textContent": text_content
        }

        try:
            response = self.session.post(f"{self.api_base}/tasks", json=task_data)
            print(f"状态码: {response.status_code}")

            assert response.status_code == 200, f"创建任务失败，状态码: {response.status_code}, 响应: {response.text}"

            task = response.json()
            task_id = task.get('id')
            assert task_id is not None, "任务ID不能为空"

            print(f"任务创建成功: {task_id}")
            print(f"源语言: {task.get('sourceLanguage')}")
            print(f"目标语言: {task.get('targetLanguages')}")
            print(f"文本内容: {text_content[:50]}...")
            print(f"状态: {task.get('status')}")

            # 验证任务数据
            assert task.get('sourceLanguage') == 'en', "源语言应该是英语"
            assert 'zh-cn' in task.get('targetLanguages', []), "目标语言应包含中文"

        except Exception as e:
            pytest.fail(f"创建任务异常: {e}")

    @pytest.mark.parametrize("audio_id", ["1", "2", "3"])
    def test_create_audio_task(self, audio_id: str):
        """测试创建音频翻译任务"""
        print(f"\n=== 测试创建音频翻译任务 (音频ID: {audio_id}) ===")

        # 查找对应的音频文件
        audio_file = self.resource_path / f"{audio_id}.mp3"

        if not audio_file.exists():
            pytest.skip(f"音频文件不存在: {audio_file}")

        # 获取对应的原始文本用于准确性验证
        original_text = self.text_data.get(audio_id, "")

        print(f"使用音频文件: {audio_file.name}")
        print(f"原始文本: {original_text[:50]}...")

        try:
            # 准备multipart数据
            with open(audio_file, 'rb') as f:
                files = {
                    'file': (audio_file.name, f, 'audio/mp3')
                }

                data = {
                    'sourceLanguage': 'en',
                    'targetLanguages': ['zh-cn', 'zh-tw', 'zh', 'en', 'en-us', 'en-gb', 'pt', 'pt-br', 'pt-pt', 'ar',
                                        'bg', 'cs', 'da', 'de', 'el', 'es', 'et', 'fi', 'fr', 'he', 'hu', 'id', 'it',
                                        'ja', 'ko', 'lt', 'lv', 'nb', 'no', 'nl', 'pl', 'ro', 'ru', 'sk', 'sl', 'sv',
                                        'th', 'tr', 'uk', 'vi'],
                    'originalText': original_text
                }

                # 临时移除Content-Type header让requests自动设置
                headers = {k: v for k, v in self.session.headers.items() if k.lower() != 'content-type'}

                response = requests.post(
                    f"{self.api_base}/tasks/audio",
                    files=files,
                    data=data,
                    headers=headers
                )

            print(f"状态码: {response.status_code}")

            assert response.status_code == 200, f"创建音频任务失败，状态码: {response.status_code}, 响应: {response.text}"

            task = response.json()
            task_id = task.get('id')
            assert task_id is not None, "任务ID不能为空"

            print(f"音频任务创建成功: {task_id}")
            print(f"音频文件路径: {task.get('audioFilePath')}")
            print(f"状态: {task.get('status')}")

            # 验证任务数据
            assert task.get('audioFilePath') is not None, "音频文件路径不能为空"

        except Exception as e:
            pytest.fail(f"创建音频任务异常: {e}")

    def test_get_task_status(self):
        """测试获取任务状态"""
        # 先创建一个任务
        text_content = list(self.text_data.values())[0] if self.text_data else "Test message"
        task_data = {
            "sourceLanguage": "en",
            "targetLanguages": ["zh-cn"],
            "textContent": text_content
        }

        response = self.session.post(f"{self.api_base}/tasks", json=task_data)
        assert response.status_code == 200
        task_id = response.json().get('id')

        print(f"\n=== 测试获取任务状态: {task_id} ===")

        try:
            response = self.session.get(f"{self.api_base}/tasks/{task_id}")
            print(f"状态码: {response.status_code}")

            assert response.status_code == 200, f"获取任务状态失败，状态码: {response.status_code}"

            task = response.json()
            print(f"任务ID: {task.get('id')}")
            print(f"状态: {task.get('status')}")
            print(f"分配节点: {task.get('assignedNodeId')}")
            print(f"创建时间: {task.get('createdAt')}")
            print(f"更新时间: {task.get('updatedAt')}")
            print(f"重试次数: {task.get('retryCount')}")

            if task.get('errorMessage'):
                print(f"错误信息: {task.get('errorMessage')}")

            # 验证任务数据
            assert task.get('id') == task_id, "返回的任务ID应该匹配"
            assert task.get('status') is not None, "任务状态不能为空"

        except Exception as e:
            pytest.fail(f"获取任务状态异常: {e}")

    def test_get_task_result(self):
        """测试获取任务结果"""
        # 先创建一个任务并等待完成
        text_content = list(self.text_data.values())[0] if self.text_data else "Test message"
        task_data = {
            "sourceLanguage": "en",
            "targetLanguages": ["zh-cn"],
            "textContent": text_content
        }

        response = self.session.post(f"{self.api_base}/tasks", json=task_data)
        assert response.status_code == 200
        task_id = response.json().get('id')

        # 等待任务完成
        self._wait_for_task_completion(task_id, 60)

        print(f"\n=== 测试获取任务结果: {task_id} ===")

        try:
            response = self.session.get(f"{self.api_base}/tasks/{task_id}/result")
            print(f"状态码: {response.status_code}")

            if response.status_code == 200:
                content_length = len(response.content)
                print(f"结果文件大小: {content_length} bytes")
                assert content_length > 0, "结果文件不能为空"

                # 保存结果文件
                result_file = f"translation_result_{task_id}.bin"
                with open(result_file, 'wb') as f:
                    f.write(response.content)
                print(f"结果已保存到: {result_file}")

            elif response.status_code == 404:
                pytest.skip("任务结果未找到，可能任务尚未完成")
            else:
                pytest.fail(f"获取任务结果失败，状态码: {response.status_code}, 响应: {response.text}")

        except Exception as e:
            pytest.fail(f"获取任务结果异常: {e}")

    @pytest.mark.parametrize("language", ["zh-cn", "ja", "ko"])
    def test_query_text(self, language: str):
        """测试查询文本"""
        # 先创建一个任务并等待完成
        text_content = list(self.text_data.values())[0] if self.text_data else "Test message"
        task_data = {
            "sourceLanguage": "en",
            "targetLanguages": [language],
            "textContent": text_content
        }

        response = self.session.post(f"{self.api_base}/tasks", json=task_data)
        assert response.status_code == 200
        task_id = response.json().get('id')

        # 等待任务完成
        self._wait_for_task_completion(task_id, 60)

        print(f"\n=== 测试查询文本: {task_id} ({language}) ===")

        params = {
            'language': language,
            'textId': 0,
            'source': 'TEXT'
        }

        try:
            response = self.session.get(f"{self.api_base}/tasks/{task_id}/text", params=params)
            print(f"状态码: {response.status_code}")

            if response.status_code == 200:
                text = response.text
                print(f"查询到的文本 ({language}): {text}")
                assert len(text) > 0, "翻译文本不能为空"
            elif response.status_code == 404:
                pytest.skip("文本未找到，可能任务尚未完成")
            else:
                pytest.fail(f"查询文本失败，状态码: {response.status_code}, 响应: {response.text}")

        except Exception as e:
            pytest.fail(f"查询文本异常: {e}")

    def test_cancel_task(self):
        """测试取消任务"""
        # 创建一个任务用于取消
        text_content = list(self.text_data.values())[0] if self.text_data else "Test message"
        task_data = {
            "sourceLanguage": "en",
            "targetLanguages": ["zh-cn"],
            "textContent": text_content
        }

        response = self.session.post(f"{self.api_base}/tasks", json=task_data)
        assert response.status_code == 200
        task_id = response.json().get('id')

        print(f"\n=== 测试取消任务: {task_id} ===")

        try:
            response = self.session.delete(f"{self.api_base}/tasks/{task_id}")
            print(f"状态码: {response.status_code}")

            assert response.status_code == 200, f"取消任务失败，状态码: {response.status_code}, 响应: {response.text}"
            print("任务取消成功")

            # 验证任务状态已更改
            time.sleep(1)
            status_response = self.session.get(f"{self.api_base}/tasks/{task_id}")
            if status_response.status_code == 200:
                task = status_response.json()
                assert task.get('status') == 'CANCELLED', "任务状态应该是CANCELLED"

        except Exception as e:
            pytest.fail(f"取消任务异常: {e}")

    def _wait_for_task_completion(self, task_id: str, timeout: int = 300) -> str:
        """等待任务完成"""
        print(f"\n等待任务完成: {task_id} (超时: {timeout}秒)")

        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self.session.get(f"{self.api_base}/tasks/{task_id}")
            if response.status_code == 200:
                task = response.json()
                status = task.get('status')

                if status in ['COMPLETED', 'FAILED', 'CANCELLED']:
                    print(f"任务最终状态: {status}")
                    return status

                print(f"当前状态: {status}, 等待中...")

            time.sleep(5)

        print("等待超时")
        return 'TIMEOUT'

    @pytest.mark.slow
    def test_multiple_audio_files(self):
        """测试多个音频文件"""
        print("\n=== 测试多个音频文件 ===")

        # 测试1.mp3到7.mp3
        for audio_id in ["1", "2", "3", "4", "5", "6", "7"]:
            audio_file = self.resource_path / f"{audio_id}.mp3"
            if audio_file.exists():
                print(f"\n--- 测试音频文件 {audio_id}.mp3 ---")

                # 创建音频任务
                original_text = self.text_data.get(audio_id, "")

                with open(audio_file, 'rb') as f:
                    files = {
                        'file': (audio_file.name, f, 'audio/mp3')
                    }

                    data = {
                        'sourceLanguage': 'en',
                        'targetLanguages': ['zh-cn', 'ja', 'ko'],
                        'originalText': original_text
                    }

                    headers = {k: v for k, v in self.session.headers.items() if k.lower() != 'content-type'}

                    response = requests.post(
                        f"{self.api_base}/tasks/audio",
                        files=files,
                        data=data,
                        headers=headers
                    )

                if response.status_code == 200:
                    task_id = response.json().get('id')
                    # 等待任务完成
                    status = self._wait_for_task_completion(task_id, 120)
                    if status == 'COMPLETED':
                        # 测试获取结果
                        result_response = self.session.get(f"{self.api_base}/tasks/{task_id}/result")
                        assert result_response.status_code == 200

                        # 测试查询不同语言的文本
                        for lang in ['zh-cn', 'ja', 'ko']:
                            params = {'language': lang, 'textId': 0, 'source': 'AUDIO'}
                            text_response = self.session.get(f"{self.api_base}/tasks/{task_id}/text", params=params)
                            if text_response.status_code == 200:
                                print(f"音频 {audio_id} 翻译结果 ({lang}): {text_response.text[:50]}...")
            else:
                print(f"音频文件不存在: {audio_file}")

    @pytest.mark.slow
    def test_multiple_text_segments(self):
        """测试多个文本段落"""
        print("\n=== 测试多个文本段落 ===")

        # 测试text.json中的所有文本段落
        for text_id, text_content in self.text_data.items():
            print(f"\n--- 测试文本段落 {text_id} ---")

            task_data = {
                "sourceLanguage": "en",
                "targetLanguages": ["zh-cn", "ja", "ko"],
                "textContent": text_content
            }

            response = self.session.post(f"{self.api_base}/tasks", json=task_data)
            if response.status_code == 200:
                task_id = response.json().get('id')
                # 等待任务完成
                status = self._wait_for_task_completion(task_id, 60)
                if status == 'COMPLETED':
                    # 测试获取结果
                    result_response = self.session.get(f"{self.api_base}/tasks/{task_id}/result")
                    assert result_response.status_code == 200

                    # 测试查询不同语言的文本
                    for lang in ['zh-cn', 'ja', 'ko']:
                        params = {'language': lang, 'textId': 0, 'source': 'TEXT'}
                        text_response = self.session.get(f"{self.api_base}/tasks/{task_id}/text", params=params)
                        if text_response.status_code == 200:
                            print(f"文本 {text_id} 翻译结果 ({lang}): {text_response.text[:50]}...")


# pytest配置
def pytest_configure(config):
    """pytest配置"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )


if __name__ == "__main__":
    # 运行pytest
    pytest.main(["-v", "--tb=short", __file__])
