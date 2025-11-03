import streamlit as st
import whisper
import google.generativeai as genai
from gtts import gTTS
import io
import tempfile  # 임시 파일 저장용 (클라우드에서)

# 언어 매핑 (5개 언어)
LANGUAGES = {'한국어': 'ko', '베트남어': 'vi', '영어': 'en', '중국어': 'zh', '일본어': 'ja'}
LANG_NAMES = list(LANGUAGES.keys())

st.title("동시 통역기 (기본: 한국어 → 베트남어, gTTS: 또렷&친근 여성 시뮬)")

# API 키 입력 UI (세션 상태로 저장)
if 'api_key' not in st.session_state:
    st.session_state.api_key = ""

api_key_input = st.text_input("Google API 키 입력 (https://aistudio.google.com/api-keys에서 발급)", 
                              value=st.session_state.api_key, 
                              type="password",
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

# 오디오 파일 업로드 (클라우드용 – 스마트폰 녹음 앱으로 wav/mp3 업로드)
uploaded_file = st.file_uploader("음성 파일 업로드 (WAV/MP3, 한국어로 말한 오디오)", type=['wav', 'mp3', 'm4a'])

if uploaded_file is not None:
    st.write("파일 업로드됐어요! 처리 중...")
    
    # 임시 파일 저장 (클라우드에서)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name
    
    # STT: 음성 → 텍스트
    result = whisper_model.transcribe(tmp_path, language=LANGUAGES[input_lang])
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
        st.info("TTS: gTTS (또렷한 여성-like 목소리). 업로드 파일로 테스트하세요!")

st.write("테스트: 스마트폰 녹음 앱으로 '안녕하세요' 말한 WAV 파일 업로드해 보세요. (실시간 업그레이드 원하시면 말씀하세요!)")

st.write("종료하려면 페이지를 새로고침하세요. 이제 에러 없이 실행될 거예요!")
