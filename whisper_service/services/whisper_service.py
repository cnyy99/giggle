import torch
import whisper  # 改为使用原始的 OpenAI Whisper
from utils.logger import setup_logger
from utils.gpu_utils import get_gpu_info

logger = setup_logger(__name__)

class WhisperService:
    def __init__(self, config):
        self.config = config
        self.device = self._setup_device()
        self.model = self._load_model()
        
    def _setup_device(self):
        """设置GPU设备"""
        if torch.cuda.is_available():
            device = "cuda"
            gpu_info = get_gpu_info()
            logger.info(f"Using GPU: {gpu_info}")
        else:
            device = "cpu"
            logger.warning("CUDA not available, using CPU")
        return device
    
    def _load_model(self):
        """加载Whisper模型"""
        model_size = self.config.WHISPER_MODEL_SIZE
        logger.info(f"Loading Whisper model: {model_size}")
        
        # 使用原始的 OpenAI Whisper
        model = whisper.load_model(model_size, device=self.device)
        logger.info("Whisper model loaded successfully")
        return model
    
    async def transcribe(self, audio_path, language=None):
        """语音转文字"""
        try:
            logger.info(f"Transcribing audio: {audio_path}")
            
            # 使用原始 Whisper 进行转录
            result = self.model.transcribe(
                audio_path,
                language=language,
                task="transcribe"
            )
            
            # 获取转录文本
            transcribed_text = result["text"].strip()
            detected_language = result["language"]
            
            logger.info(f"Transcription completed. Language: {detected_language}")
            return transcribed_text
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise
    
    def get_supported_languages(self):
        """获取支持的语言列表"""
        # 原始 Whisper 支持的语言（与 faster-whisper 相同）
        return [
            'en', 'zh', 'de', 'es', 'ru', 'ko', 'fr', 'ja', 'pt', 'tr', 'pl', 'ca', 'nl', 
            'ar', 'sv', 'it', 'id', 'hi', 'fi', 'vi', 'he', 'uk', 'el', 'ms', 'cs', 'ro', 
            'da', 'hu', 'ta', 'no', 'th', 'ur', 'hr', 'bg', 'lt', 'la', 'mi', 'ml', 'cy', 
            'sk', 'te', 'fa', 'lv', 'bn', 'sr', 'az', 'sl', 'kn', 'et', 'mk', 'br', 'eu', 
            'is', 'hy', 'ne', 'mn', 'bs', 'kk', 'sq', 'sw', 'gl', 'mr', 'pa', 'si', 'km', 
            'sn', 'yo', 'so', 'af', 'oc', 'ka', 'be', 'tg', 'sd', 'gu', 'am', 'yi', 'lo', 
            'uz', 'fo', 'ht', 'ps', 'tk', 'nn', 'mt', 'sa', 'lb', 'my', 'bo', 'tl', 'mg', 
            'as', 'tt', 'haw', 'ln', 'ha', 'ba', 'jw', 'su'
        ]