# backend/main.py
"""
Core Business Logic Module
This module contains all functions related to AI model interaction,
data processing, and business workflows. It is decoupled from the
web framework (FastAPI).
"""

import io
import re
import logging
import time
import hashlib
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional, Tuple, List
from pathlib import Path
# from pydub import AudioSegment
# from pydub.effects import normalize
import json
import tempfile
import os

import requests
# import scipy.io.wavfile
# import torch
# import numpy as np
# from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline, VitsModel, AutoTokenizer
# from openai import OpenAI
from mistralai import Mistral
from cachetools import TTLCache # 确保导入 TTLCache

# Relative imports from within the project
from .prompt_managements import pm
from .models import ChatMessage, MessageRole, format_dialog_for_display
# from .audio_processor import AudioProcessor, concatenate_audios_sync
from .models import TranslateRequest, TranslateResponse, TranslationStyle


# --- ADDED START: Word Report Cache and Logic ---
word_report_cache = TTLCache(maxsize=200, ttl=3600) # Cache reports for 24 hours

# Configure logging
logger = logging.getLogger(__name__)

# --- Global Singletons and Processors ---

class ModelManager:
    """
    Singleton class to manage shared resources like thread pools.
    """
    _instance = None
    _executor = ThreadPoolExecutor(max_workers=2) # 保留线程池给异步任务使用

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

model_manager = ModelManager()
# audio_processor = AudioProcessor()

# --- Core Business Logic Functions ---

LANGUAGE_NAME_MAP = {
    "zh": "Chinese (中文)",
    "ko": "Korean (한국어)",
    "ur": "Urdu (اردو)",
    "hi": "Hindi (हिन्दी)",
    "uk": "Ukrainian (Українська)",
    "ru": "Russian (Русский)",
    "vi": "Vietnamese (Tiếng Việt)"
}

async def generate_word_report(swedish_word: str, word_class: str, target_language: str) -> Dict[str, Any]:
    """
    Generates a structured learning report for a Swedish word in a target language.
    """
    cache_key = f"report_{swedish_word}_{word_class}_{target_language}"
    if cache_key in word_report_cache:
        logger.info(f"Cache HIT for word report: {swedish_word} in {target_language}")
        return word_report_cache[cache_key]

    logger.info(f"Cache MISS for word report: {swedish_word} in {target_language}. Generating new one.")
    
    language_full_name = LANGUAGE_NAME_MAP.get(target_language, target_language.capitalize())

    # 如果词性未提供或为空，就用一个描述性短语代替
    effective_word_class = word_class if word_class else "unknown"

    prompt = pm.get_prompt(
        name="word_analysis_prompt",
        variables={
            "SwedishWord": swedish_word,
            "WordClass": effective_word_class,
            "TargetLanguage": language_full_name
        }
    )

    # 使用低温以获得更稳定、结构化的输出
    raw_response, _ = await generate_response_async(
        scenario_prompt=prompt,
        chat_history=[],
        generation_config={"temperature": 0.1, "maxOutputTokens": 1024}
    )

    try:
        # 清理并解析LLM返回的JSON字符串
        # 有时LLM会用 markdown 代码块包裹JSON
        clean_response = re.sub(r'```json\n(.*?)\n```', r'\1', raw_response, flags=re.DOTALL).strip()
        report_data = json.loads(clean_response)
        
        # 将结果存入缓存
        word_report_cache[cache_key] = report_data
        return report_data
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Failed to parse JSON response from LLM for word '{swedish_word}': {e}")
        logger.error(f"LLM Raw Response was: {raw_response}")
        raise ValueError("The AI returned a response in an invalid format.")

# def transcribe_audio(audio_data: bytes, input_format: str = 'webm') -> Tuple[str, float]:
#     """
#     Transcribes audio data to text using the Whisper model.
    
#     Args:
#         audio_data (bytes): The raw audio data.
#         input_format (str): The format of the input audio.
        
#     Returns:
#         A tuple containing the transcribed text and the processing duration.
#     """
#     start_time = time.time()
#     if not audio_data:
#         raise ValueError("Audio data is empty.")
    
#     simple_format = input_format.split('/')[1].split(';')[0] if input_format else 'webm'
    
#     # Use temporary files for robust processing with pydub and the model
#     temp_input_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{simple_format}")
#     temp_input_path = temp_input_file.name
#     temp_input_file.write(audio_data)
#     temp_input_file.close()

#     temp_wav_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
#     temp_wav_path = temp_wav_file.name
#     temp_wav_file.close()

#     try:
#         audio = AudioSegment.from_file(temp_input_path, format=simple_format)
#         audio = audio.set_channels(1).set_frame_rate(16000)
#         audio = normalize(audio, headroom=0.1)
#         audio.export(temp_wav_path, format="wav")

#         whisper_pipeline = model_manager.get_whisper_model()
#         result = whisper_pipeline(temp_wav_path, generate_kwargs={"language": "swedish"})
#         text = result["text"]

#         duration = time.time() - start_time
#         logger.info(f"Audio transcribed in {duration:.2f}s. Text: '{text[:50]}...'")
#         return text, duration
#     except Exception as e:
#         logger.error(f"Transcription failed: {e}", exc_info=True)
#         raise RuntimeError(f"Audio transcription failed: {e}")
#     finally:
#         # Ensure temporary files are cleaned up
#         if os.path.exists(temp_input_path): os.remove(temp_input_path)
#         if os.path.exists(temp_wav_path): os.remove(temp_wav_path)

# async def transcribe_audio_async(audio_data: bytes, input_format: str = 'webm') -> Tuple[str, float]:
#     """Asynchronously transcribes audio."""
#     loop = asyncio.get_event_loop()
#     return await loop.run_in_executor(model_manager._executor, transcribe_audio, audio_data, input_format)

def _call_mistral_primary(
    scenario_prompt: str,
    chat_history: List[ChatMessage],
    generation_config: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, float]]:
    """
    Calls the Mistral AI API (primary LLM).
    """
    logger.info("Attempting to generate response with primary API (Mistral)...")
    timing_log = {}
    total_start_time = time.time()

    # 1. Use Mistral's environment variables
    api_key = os.getenv("MISTRAL_API_KEY")
    model_name = os.getenv("MISTRAL_MODEL_NAME", "open-mistral-7b") # Your requested model

    if not api_key:
        raise ValueError("MISTRAL_API_KEY environment variable not set.")

    # 2. Initialize the Mistral client
    client = Mistral(api_key=api_key)

    # Message formatting is the same, so no changes needed here
    messages = [{"role": "system", "content": scenario_prompt}]
    for msg in chat_history:
        if isinstance(msg, ChatMessage) and msg.content and msg.content.strip():
            role = "assistant" if msg.role == MessageRole.AI else "user"
            messages.append({"role": role, "content": msg.content})

    try:
        api_call_start_time = time.time()

        # 3. Use the Mistral client's chat.completions method
        # Note: The official client is `chat`, but `chat.completions` is also supported for OpenAI compatibility.
        # We will use the documented `chat` method for clarity.
        response = client.chat(
            model=model_name,
            messages=messages,
            temperature=generation_config.get("temperature", 0.8) if generation_config else 0.8,
            # Note: Mistral uses 'max_tokens' just like OpenAI
            max_tokens=generation_config.get("maxOutputTokens", 2048) if generation_config else 2048,
        )
        timing_log["api_call_time"] = time.time() - api_call_start_time

        # 4. The response structure is the same
        model_response = response.choices[0].message.content
        timing_log["total_response_time"] = time.time() - total_start_time

        logger.info(f"Generated AI response successfully with Mistral in {timing_log['total_response_time']:.2f}s.")
        return model_response, timing_log

    except Exception as e:
        logger.error(f"Mistral API request failed: {e}", exc_info=True)
        raise # Re-raise the exception to be handled by the scheduler

# def _call_deepseek_primary(
#     scenario_prompt: str,
#     chat_history: List[ChatMessage],
#     generation_config: Optional[Dict[str, Any]] = None
# ) -> Tuple[str, Dict[str, float]]:
#     """
#     Calls the DeepSeek API (primary LLM).
#     """
#     logger.info("Attempting to generate response with primary API (DeepSeek)...")
#     timing_log = {}
#     total_start_time = time.time()
    
#     api_key = os.getenv("DEEPSEEK_API_KEY")
#     base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
#     model_name = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")

#     if not api_key:
#         raise ValueError("DEEPSEEK_API_KEY environment variable not set.")

#     client = OpenAI(api_key=api_key, base_url=base_url)

#     # Convert chat history to the OpenAI/DeepSeek format
#     messages = [{"role": "system", "content": scenario_prompt}]
#     for msg in chat_history:
#         if isinstance(msg, ChatMessage) and msg.content and msg.content.strip():
#             # Map internal 'ai' role to 'assistant'
#             role = "assistant" if msg.role == MessageRole.AI else "user"
#             messages.append({"role": role, "content": msg.content})

#     try:
#         api_call_start_time = time.time()
#         response = client.chat.completions.create(
#             model=model_name,
#             messages=messages,
#             stream=False,
#             temperature=generation_config.get("temperature", 0.8) if generation_config else 0.8,
#             max_tokens=generation_config.get("maxOutputTokens", 2048) if generation_config else 2048,
#         )
#         timing_log["api_call_time"] = time.time() - api_call_start_time
        
#         model_response = response.choices[0].message.content
#         timing_log["total_response_time"] = time.time() - total_start_time
        
#         logger.info(f"Generated AI response successfully with DeepSeek in {timing_log['total_response_time']:.2f}s.")
#         return model_response, timing_log

#     except Exception as e:
#         logger.error(f"DeepSeek API request failed: {e}", exc_info=True)
#         raise # Re-raise the exception to be handled by the scheduler

def _call_gemini_fallback(
    scenario_prompt: str,
    chat_history: List[ChatMessage],
    generation_config: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, float]]:
    """
    Calls the Gemini API (fallback LLM).
    """
    logger.info("Attempting to generate response with fallback API (Gemini)...")
    timing_log = {}
    total_start_time = time.time()

    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")

    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set for fallback.")

    headers = {"Content-Type": "application/json"}
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    contents = []
    if scenario_prompt:
        contents.append({"role": "user", "parts": [{"text": scenario_prompt}]})
        contents.append({"role": "model", "parts": [{"text": "Ok, jag förstår. Låt oss börja."}]}) # OK, I understand. Let's begin.
    
    for msg in chat_history:
        if isinstance(msg, ChatMessage) and msg.content and msg.content.strip():
            role = "model" if msg.role == MessageRole.AI else "user"
            contents.append({"role": role, "parts": [{"text": msg.content}]})

    final_generation_config = {
        "temperature": 0.8, "topP": 0.95, "maxOutputTokens": 2048,
    }
    if generation_config:
        final_generation_config.update(generation_config)

    payload = {"contents": contents, "generationConfig": final_generation_config}

    try:
        api_call_start_time = time.time()
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        timing_log["api_call_time"] = time.time() - api_call_start_time
        response.raise_for_status()
        response_json = response.json()

        if 'candidates' not in response_json or not response_json['candidates']:
            feedback = response_json.get('promptFeedback', {})
            block_reason = feedback.get('blockReason', 'Unknown reason')
            raise ValueError(f"Response blocked by Gemini API. Reason: {block_reason}")

        model_response = response_json['candidates'][0]['content']['parts'][0]['text']
        timing_log["total_response_time"] = time.time() - total_start_time
        
        logger.info(f"Generated AI response successfully with Gemini (fallback) in {timing_log['total_response_time']:.2f}s.")
        return model_response, timing_log
    except Exception as e:
        logger.error(f"Gemini fallback API request failed: {e}", exc_info=True)
        raise

def generate_response(
    scenario_prompt: str,
    chat_history: List[ChatMessage],
    generation_config: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, float]]:
    """
    Intelligent dispatcher for generating AI responses.
    It first tries the primary API (DeepSeek) and falls back to the secondary API (Gemini) on failure.
    """

    try:
        # Step 1: Attempt the primary API (Mistral)
        return _call_mistral_primary(scenario_prompt, chat_history, generation_config)
        # return _call_deepseek_primary(scenario_prompt, chat_history, generation_config)
    except Exception as e:
        logger.warning(f"Primary API (Mistral) failed: {e}. Falling back to Gemini.")

        try:
            # Step 2: Attempt the fallback API (Gemini)
            return _call_gemini_fallback(scenario_prompt, chat_history, generation_config)
        except Exception as fallback_e:
            logger.critical(f"Fallback API (Gemini) also failed: {fallback_e}. No API available to generate response.")
            # Raise the final exception when both APIs fail
            raise RuntimeError(f"Both primary and fallback APIs failed. Last error: {fallback_e}")


async def generate_response_async(
    scenario_prompt: str,
    chat_history: List[ChatMessage],
    generation_config: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, float]]:
    """Asynchronously executes the AI response generation dispatch."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        model_manager._executor,
        generate_response,
        scenario_prompt,
        chat_history,
        generation_config
    )

# def generate_audio(text: str) -> Tuple[bytes, Dict[str, float]]:
#     """
#     Generates MP3 audio from text using the TTS model.
#     Checks for cached audio before generating.
#     """
#     timing_log = {}
#     total_start_time = time.time()
    
#     cached_audio = model_manager.get_cached_audio(text)
#     if cached_audio:
#         timing_log["cache_hit"] = True
#         timing_log["total_audio_gen_time"] = time.time() - total_start_time
#         return cached_audio, timing_log
        
#     try:
#         tts_components = model_manager.get_tts_model()
#         model, tokenizer = tts_components['model'], tts_components['tokenizer']
        
#         text_clean = text.strip() or " " # Ensure input is not empty
#         inputs = tokenizer(text_clean, return_tensors="pt").to(model_manager.device)
        
#         if 'input_ids' in inputs and inputs['input_ids'].dtype != torch.long:
#             inputs['input_ids'] = inputs['input_ids'].long()
            
#         with torch.no_grad():
#             output = model(**inputs).waveform
            
#         waveform = output.squeeze().cpu().numpy()
#         waveform_int16 = (waveform * 32767).astype(np.int16)
        
#         audio_segment = AudioSegment(
#             waveform_int16.tobytes(), frame_rate=model.config.sampling_rate,
#             sample_width=waveform_int16.dtype.itemsize, channels=1
#         )

#         # Normalize boosts the volume to a peak level without distortion.
#         normalized_segment = normalize(audio_segment)

#         # Optionally, increase the volume by an additional 6 dB.
#         # Adjust this value carefully to avoid clipping distortion.
#         louder_segment = normalized_segment + 6 

#         buffer = io.BytesIO()
#         louder_segment.export(buffer, format="mp3", bitrate="128k")
#         buffer.seek(0)
        
#         audio_data = buffer.read()
#         model_manager.cache_audio(text, audio_data)
        
#         timing_log["cache_hit"] = False
#         timing_log["total_audio_gen_time"] = time.time() - total_start_time
#         logger.info(f"Generated MP3 audio in {timing_log['total_audio_gen_time']:.2f}s.")
        
#         return audio_data, timing_log
#     except Exception as e:
#         logger.error(f"Audio generation failed: {e}", exc_info=True)
#         raise RuntimeError(f"Audio generation failed: {e}")


# async def generate_audio_async(text: str) -> Tuple[bytes, Dict[str, float]]:
#     """Asynchronously generates audio."""
#     loop = asyncio.get_event_loop()
#     return await loop.run_in_executor(model_manager._executor, generate_audio, text)


def generate_example_dialogue(
    context_prompt: str,
) -> Tuple[str, List[str], Dict[str, float]]:
    """
    Generates an example dialogue and extracts key phrases.
    """
    start_time = time.time()
    raw_text, timing_log = generate_response(
        scenario_prompt=context_prompt,
        chat_history=[]
    )
    
    dialog_text = raw_text
    key_phrases = []
    
    # Extract key phrases section from the raw text
    key_phrases_match = re.search(r'\*\*Key Expressions:\*\*(.*)', raw_text, re.DOTALL | re.IGNORECASE)
    if key_phrases_match:
        phrases_section = key_phrases_match.group(1).strip()
        key_phrases = [line.strip().lstrip('- ') for line in phrases_section.split('\n') if line.strip()]
        dialog_text = raw_text[:key_phrases_match.start()].strip()
        
    timing_log["total_generation_time"] = time.time() - start_time
    return dialog_text, key_phrases, timing_log


def _parse_review_text(review_text: str) -> dict:
    """Parses the structured review text from the LLM response."""
    strengths = re.findall(r'-\s*(.*)', review_text.split("Strengths:")[-1].split("Areas for Improvement:")[0])
    improvements = re.findall(r'-\s*(.*)', review_text.split("Areas for Improvement:")[-1].split("Score:")[0])
    score_match = re.search(r'Score:\s*(\d+)\s*/\s*5', review_text)
    score = int(score_match.group(1)) if score_match else 0
    return {"strengths": [s.strip() for s in strengths], "improvements": [i.strip() for i in improvements], "score": score}


def generate_review(
    conversation_history: List[dict],
    level: str,
    scenario_context: str,
) -> Tuple[str, List[str], List[str], int, Dict[str, float]]:
    """
    Generates a performance review for a conversation.
    """
    start_time = time.time()
    formatted_conversation = format_dialog_for_display(conversation_history)
    prompt = pm.get_prompt(
        name="review",
        variables={"context": scenario_context, "conversation": formatted_conversation, "CEFR_Level": level}
    )
    
    raw_review_text, timing_log = generate_response(
        scenario_prompt=prompt,
        chat_history=[]
    )
    
    parsed_data = _parse_review_text(raw_review_text)
    timing_log["generation_time"] = time.time() - start_time
    return (raw_review_text, parsed_data["strengths"], parsed_data["improvements"], parsed_data["score"], timing_log)

async def start_background_tasks():
    """Initializes background tasks for the application."""
    logger.info("Starting background tasks...")
    # asyncio.create_task(model_manager.cleanup_cache())

async def generate_translation(request: TranslateRequest) -> str:
    """
    Generates a Swedish translation for a given text based on style.
    """
    style_description = "colloquial (vardaglig)" if request.style == TranslationStyle.COLLOQUIAL else "formal (formell)"
    
    # Use the existing language map to get the full name for the prompt
    language_full_name = LANGUAGE_NAME_MAP.get(request.target_language, "English")

    prompt = pm.get_prompt(
        name="translation_prompt",
        variables={
            "Style": style_description,
            "Text": request.text,
            "TargetLanguage": language_full_name
        }
    )
    
    # Using a lower temperature for more predictable translation
    translated_text, _ = await generate_response_async(
        scenario_prompt=prompt,
        chat_history=[],
        generation_config={"temperature": 0.2}
    )
    
    return translated_text.strip()