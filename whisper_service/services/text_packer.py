import struct
import json
import time
import zlib
from typing import Dict, List, Optional, Tuple
from utils.logger import setup_logger
import hashlib

logger = setup_logger(__name__)


class SimplifiedTextPacker:
    """简化的高效文本打包器 - 去除语言hash"""

    def __init__(self):
        self.version = 4
        self.HEADER_SIZE = 16  # 版本 + 语言数量 + 语言索引偏移 + 文本数据偏移
        self.LANG_ENTRY_SIZE = 8  # 2字节语言代码长度 + 6字节保留(可存储语言代码)
        self.LANG_INDEX_ITEM_SIZE = 10  # 语言代码hash + 文本索引偏移 + 文本数量
        self.TEXT_INDEX_ITEM_SIZE = 20  # task_id(8字节) + 偏移(4) + 长度(4) + 源类型(2) + 保留(2)

    @staticmethod
    def deterministic_hash(text: str) -> int:
        """生成确定性的32位hash值"""
        return int(hashlib.md5(text.encode('utf-8')).hexdigest()[:8], 16)

    def pack_multiple_translations(self, tasks_data: List[Dict]) -> bytes:
        """批量打包多个任务的翻译数据

        Args:
            tasks_data: 任务数据列表，每个元素包含:
                {
                    'task_id': str,
                    'original_text': Optional[str],
                    'original_translations': Optional[Dict[str, str]],
                    'stt_text': Optional[str],
                    'stt_translations': Optional[Dict[str, str]]
                }

        Returns:
            bytes: 打包后的二进制数据
        """
        try:
            # 收集所有语言
            all_languages = set()
            for task_data in tasks_data:
                if task_data.get('original_translations'):
                    all_languages.update(task_data['original_translations'].keys())
                if task_data.get('stt_translations'):
                    all_languages.update(task_data['stt_translations'].keys())

            if not all_languages:
                # 如果没有任何翻译数据，返回空的打包数据
                header = struct.pack('<IIII', self.version, 0, self.HEADER_SIZE, self.HEADER_SIZE)
                return header

            # 构建语言表（直接存储语言代码）
            lang_table = b''
            lang_offsets = {}

            for lang_code in sorted(all_languages):
                lang_bytes = lang_code.encode('utf-8')
                lang_table += struct.pack('<H', len(lang_bytes)) + lang_bytes.ljust(6, b'\x00')
                lang_offsets[lang_code] = len(lang_table) - 8

            # 准备文本数据和索引
            lang_data = {}
            text_data_parts = []
            current_offset = 0

            # 处理每个任务的数据
            for task_data in tasks_data:
                task_id = task_data['task_id']
                original_text = task_data.get('original_text')
                original_translations = task_data.get('original_translations')
                stt_text = task_data.get('stt_text')
                stt_translations = task_data.get('stt_translations')

                # 使用固定长度的task_id（8字节）
                task_id_bytes = task_id.encode('utf-8')[:8].ljust(8, b'\x00')

                # 处理原始文本翻译
                if original_text and original_translations:
                    for lang_code, text in original_translations.items():
                        if lang_code not in lang_data:
                            lang_data[lang_code] = []

                        text_bytes = text.encode('utf-8')
                        compressed_text = zlib.compress(text_bytes, level=9)

                        lang_data[lang_code].append({
                            'task_id_bytes': task_id_bytes,
                            'offset': current_offset,
                            'length': len(compressed_text),
                            'source_type': 0  # TEXT
                        })

                        text_data_parts.append(compressed_text)
                        current_offset += len(compressed_text)

                # 处理STT文本翻译
                if stt_text and stt_translations:
                    for lang_code, text in stt_translations.items():
                        if lang_code not in lang_data:
                            lang_data[lang_code] = []

                        text_bytes = text.encode('utf-8')
                        compressed_text = zlib.compress(text_bytes, level=9)

                        lang_data[lang_code].append({
                            'task_id_bytes': task_id_bytes,
                            'offset': current_offset,
                            'length': len(compressed_text),
                            'source_type': 1  # AUDIO
                        })

                        text_data_parts.append(compressed_text)
                        current_offset += len(compressed_text)

            # 构建语言索引和文本索引
            lang_index_data = b''
            text_index_data = b''
            text_index_offset = 0

            for lang_code in sorted(lang_data.keys()):
                texts = lang_data[lang_code]
                lang_hash = self.deterministic_hash(lang_code)

                # 语言索引项
                lang_index_data += struct.pack('<III', lang_hash, text_index_offset, len(texts))

                # 文本索引项
                for text_info in texts:
                    text_index_data += struct.pack('<8sIIHH',
                                                   text_info['task_id_bytes'],
                                                   text_info['offset'],
                                                   text_info['length'],
                                                   text_info['source_type'],
                                                   0)  # 保留字段
                    text_index_offset += self.TEXT_INDEX_ITEM_SIZE

            # 计算偏移
            lang_table_offset = self.HEADER_SIZE
            lang_index_offset = lang_table_offset + len(lang_table)
            text_index_offset = lang_index_offset + len(lang_index_data)
            text_data_offset = text_index_offset + len(text_index_data)

            # 构建文件头
            header = struct.pack('<IIII',
                                 self.version,
                                 len(all_languages),
                                 lang_index_offset,
                                 text_data_offset)

            # 组装最终数据
            result = (header + lang_table + lang_index_data +
                      text_index_data + b''.join(text_data_parts))

            return result

        except Exception as e:
            logger.error(f"Failed to pack multiple translations: {e}")
            raise

    def pack_translations(self, task_id: str,
                          original_text: Optional[str],
                          original_translations: Optional[Dict[str, str]],
                          stt_text: Optional[str],
                          stt_translations: Optional[Dict[str, str]]) -> bytes:
        """单个任务的打包方法 - 兼容性保持"""
        # 将单个任务数据转换为批量格式
        tasks_data = [{
            'task_id': task_id,
            'original_text': original_text,
            'original_translations': original_translations,
            'stt_text': stt_text,
            'stt_translations': stt_translations
        }]
        return self.pack_multiple_translations(tasks_data)

    def query_text(self, packed_data: bytes, language: str, task_id: str, source_type: str) -> Optional[str]:
        """通过 语言 -> task_id -> 文本来源 查询文本内容"""
        try:
            if len(packed_data) < self.HEADER_SIZE:
                return None

            # 解析文件头
            version, lang_count, lang_index_offset, text_data_offset = \
                struct.unpack('<IIII', packed_data[:self.HEADER_SIZE])

            # 查找语言索引
            lang_hash = self.deterministic_hash(language)
            text_index_start = None
            text_count = 0

            # 遍历语言索引找到匹配的语言
            for i in range(lang_count):
                pos = lang_index_offset + i * 12  # 语言索引项大小：4+4+4=12字节
                if pos + 12 <= len(packed_data):
                    stored_hash, text_offset, count = struct.unpack('<III', packed_data[pos:pos + 12])
                    if stored_hash == lang_hash:
                        # 文本索引的起始位置 = 语言索引结束位置 + 当前语言的文本偏移
                        text_index_start = lang_index_offset + lang_count * 12 + text_offset
                        text_count = count
                        break

            if text_index_start is None:
                return None

            # 准备查询参数 - 修复源类型验证
            task_id_bytes = task_id.encode('utf-8')[:8].ljust(8, b'\x00')

            # 严格验证源类型
            source_type_upper = source_type.upper()
            if source_type_upper == "TEXT":
                source_type_code = 0
            elif source_type_upper == "AUDIO":
                source_type_code = 1
            else:
                # 无效的源类型，直接返回 None
                return None

            # 查找文本索引
            for i in range(text_count):
                pos = text_index_start + i * self.TEXT_INDEX_ITEM_SIZE
                if pos + self.TEXT_INDEX_ITEM_SIZE <= len(packed_data):
                    stored_task_id, data_offset, data_length, stored_source_type, _ = \
                        struct.unpack('<8sIIHH', packed_data[pos:pos + self.TEXT_INDEX_ITEM_SIZE])

                    if stored_task_id == task_id_bytes and stored_source_type == source_type_code:
                        # 读取并解压缩文本数据
                        text_start = text_data_offset + data_offset
                        text_end = text_start + data_length

                        if text_end <= len(packed_data):
                            compressed_data = packed_data[text_start:text_end]
                            decompressed_data = zlib.decompress(compressed_data)
                            return decompressed_data.decode('utf-8')

            return None

        except Exception as e:
            logger.error(f"Failed to query text: {e}")
            return None


if __name__ == '__main__':
    """测试 SimplifiedTextPacker 的功能"""
    print("=== SimplifiedTextPacker 测试开始 ===")

    packer = SimplifiedTextPacker()

    # 测试数据
    test_data = [
        {
            'task_id': 'task001',
            'original_text': 'Hello world',
            'original_translations': {
                'zh': '你好世界',
                'ja': 'こんにちは世界',
                'ko': '안녕하세요 세계',
                'fr': 'Bonjour le monde',
                'de': 'Hallo Welt'
            },
            'stt_text': 'Hello world audio',
            'stt_translations': {
                'zh': '你好世界音频',
                'ja': 'こんにちは世界オーディオ',
                'ko': '안녕하세요 세계 오디오',
                'fr': 'Bonjour le monde audio',
                'de': 'Hallo Welt Audio'
            }
        },
        {
            'task_id': 'task002',
            'original_text': 'Good morning',
            'original_translations': {
                'zh': '早上好',
                'ja': 'おはよう',
                'ko': '좋은 아침',
                'fr': 'Bonjour',
                'es': 'Buenos días'
            },
            'stt_text': 'Good morning audio',
            'stt_translations': {
                'zh': '早上好音频',
                'ja': 'おはようオーディオ',
                'ko': '좋은 아침 오디오',
                'fr': 'Bonjour audio',
                'es': 'Buenos días audio'
            }
        }
    ]
    # packed1 = packer.pack_multiple_translations(test_data)
    # with open('/tmp/test.bin', 'wb') as f:
    #     f.write(packed1)

    # read from file
    with open('/tmp/translation_results/6ed9f763-1af6-47b1-aec1-e39a928f7589.bin', 'rb') as f:
        packed = f.read()

    # print(packed == packed1)
    # print(packed)
    # print(packed1)
    # 2. 测试查询功能
    test_queries = [
        ('zh', '6ed9f763-1af6-47b1-aec1-e39a928f7589', 'TEXT'),
        ('ja', '6ed9f763-1af6-47b1-aec1-e39a928f7589', 'AUDIO'),
        ('fr', '6ed9f763-1af6-47b1-aec1-e39a928f7589', 'TEXT'),
        ('es', '6ed9f763-1af6-47b1-aec1-e39a928f7589', 'AUDIO'),
        ('ko', '6ed9f763-1af6-47b1-aec1-e39a928f7589', 'TEXT'),
    ]

    for lang, task_id, source_type in test_queries:
        try:
            result = packer.query_text(packed, lang, task_id, source_type)
            if result:
                print(f"✓ 查询成功 [{lang}][{task_id}][{source_type}]: {result}")
            else:
                print(f"○ 查询无结果 [{lang}][{task_id}][{source_type}]")
        except Exception as e:
            print(f"✗ 查询失败 [{lang}][{task_id}][{source_type}]: {e}")

    # 3. 测试边界情况
    print("\n3. 测试边界情况...")

    # 测试空数据
    try:
        empty_packed = packer.pack_translations(
            task_id='empty',
            original_text=None,
            original_translations=None,
            stt_text=None,
            stt_translations=None
        )
        print(f"✓ 空数据打包成功, 大小: {len(empty_packed)} 字节")
    except Exception as e:
        print(f"✗ 空数据打包失败: {e}")

    # 测试长 task_id
    try:
        long_task_id = 'very_long_task_id_that_exceeds_8_bytes'
        long_packed = packer.pack_translations(
            task_id=long_task_id,
            original_text='Test',
            original_translations={'en': 'Test'},
            stt_text=None,
            stt_translations=None
        )
        result = packer.query_text(long_packed, 'en', long_task_id, 'TEXT')
        print(f"✓ 长 task_id 测试成功: {result}")
    except Exception as e:
        print(f"✗ 长 task_id 测试失败: {e}")

    # 测试特殊字符
    try:
        special_packed = packer.pack_translations(
            task_id='special',
            original_text='Special chars: 🌟💫⭐',
            original_translations={
                'zh': '特殊字符: 🌟💫⭐',
                'emoji': '🌟💫⭐🎉🎊'
            },
            stt_text=None,
            stt_translations=None
        )
        result = packer.query_text(special_packed, 'emoji', 'special', 'TEXT')
        print(f"✓ 特殊字符测试成功: {result}")
    except Exception as e:
        print(f"✗ 特殊字符测试失败: {e}")
