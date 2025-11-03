import streamlit as st
import whisper
import google.generativeai as genai
from gtts import gTTS  # TTS 전용 import (gTTS 사용)
import io
import pyaudio
import wave

# 언어 매핑 (5개 언어)
LANGUAGES = {'한국어': 'ko', '베트남어': 'vi', '영어': 'en', '중국어': 'zh', '일본어': 'ja'}
LANG_NAMES = list(LANGUAGES.keys())

st.title("동시 통역기 (기본: 한국어 → 베트남어, gTTS: 또렷&친근 여성 시뮬)")

# API 키 입력 UI (세션 상태로 저장)
if 'api_key' not in st.session_state:
    st.session_state.api_key = ""

api_key_input = st.text_input("Google API 키 입력 (https://aistudio.google.com/api-keys에서 발급)", 
                              value=st.session_state.api_key, 
                              type="password",  # 보안 위해 마스킹
                              help="API 키를 입력하세요. 저장되어 재사용됩니다.")

if api_key_input:
    st.session_state.api_key = api_key_input
    API_KEY = api_key_input
else:
    st.warning("API 키를 입력하세요! (Gemini 번역에 필요)")
    st.stop()

# Google Gemini API 설정
genai.configure(api_key=API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

# Whisper 모델 로드
@st.cache_resource
def load_whisper():
    return whisper.load_model("base")

whisper_model = load_whisper()

# 기본값 설정: 입력 - 한국어, 출력 - 베트남어
if 'input_lang' not in st.session_state:
    st.session_state.input_lang = '한국어'
if 'output_lang' not in st.session_state:
    st.session_state.output_lang = '베트남어'

# 언어 선택 (기본값 적용)
input_lang = st.selectbox("입력 언어", LANG_NAMES, index=LANG_NAMES.index(st.session_state.input_lang), key='input_select')
output_lang = st.selectbox("출력 언어", LANG_NAMES, index=LANG_NAMES.index(st.session_state.output_lang), key='output_select')

# 세션 상태 업데이트
st.session_state.input_lang = input_lang
st.session_state.output_lang = output_lang

# 언어 전환 버튼 (쌍방향)
if st.button("언어 전환 (A ↔ B)"):
    temp = st.session_state.input_lang
    st.session_state.input_lang = st.session_state.output_lang
    st.session_state.output_lang = temp
    st.rerun()

# 시작 버튼
if st.button("시작 (음성 입력)"):
    st.write("마이크를 켜고 말하세요. (테스트: 5초 녹음 후 처리)")
    
    # 마이크 녹음 설정
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    RECORD_SECONDS = 5
    
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    
    frames = []
    for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        frames.append(data)
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # WAV 파일 임시 저장
    wf = wave.open("input.wav", 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    
    # STT: 음성 → 텍스트
    result = whisper_model.transcribe("input.wav", language=LANGUAGES[input_lang])
    text = result["text"].strip()
    st.write(f"인식된 텍스트 ({input_lang}): {text}")
    
    if not text:
        st.warning("음성을 인식하지 못했습니다. 다시 시도하세요.")
    else:
        # Gemini AI 번역
        prompt = f"""
        다음 텍스트를 {output_lang}로 전문 통역사처럼 자연스럽고 정확하게 번역하세요. 
        구어체를 유지하며, 문화적 맥락과 뉘앙스를 고려하세요. 간결하게 유지하세요.
        
        원문 ({input_lang}): {text}
        """
        
        response = gemini_model.generate_content(prompt)
        translated_text = response.text.strip()
        st.write(f"번역 결과 ({output_lang}) - Gemini AI: {translated_text}")
        
        # TTS: gTTS 사용 (자연스러운 여성-like 목소리 시뮬: slow=False로 또렷&친근하게)
        tts = gTTS(translated_text, lang=LANGUAGES[output_lang], slow=False)
        audio_file = io.BytesIO()
        tts.write_to_fp(audio_file)
        audio_file.seek(0)
        st.audio(audio_file, format='audio/mp3')
        st.info("TTS: gTTS (또렷한 여성-like 목소리). 더 고급 TTS 원하시면 Google Cloud JSON 키 설정 도와드릴게요.")

st.write("종료하려면 페이지를 새로고침하세요. 이제 에러 없이 실행될 거예요!")
