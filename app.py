import streamlit as st
import whisper
import google.generativeai as genai
from gtts import gTTS
import io
import tempfile
import base64  # JS 오디오 데이터 처리용

# 언어 매핑 (5개 언어)
LANGUAGES = {'한국어': 'ko', '베트남어': 'vi', '영어': 'en', '중국어': 'zh', '일본어': 'ja'}
LANG_NAMES = list(LANGUAGES.keys())

st.title("동시 통역기 (실시간 마이크: 말하면 자동 인식 → 번역 → 음성 출력)")

# API 키 입력 UI
if 'api_key' not in st.session_state:
    st.session_state.api_key = ""

api_key_input = st.text_input("Google API 키 입력 (https://aistudio.google.com/api-keys에서 발급)", 
                              value=st.session_state.api_key, 
                              type="password")

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

# 기본값 설정
if 'input_lang' not in st.session_state:
    st.session_state.input_lang = '한국어'
if 'output_lang' not in st.session_state:
    st.session_state.output_lang = '베트남어'

# 언어 선택
input_lang = st.selectbox("입력 언어", LANG_NAMES, index=LANG_NAMES.index(st.session_state.input_lang), key='input_select')
output_lang = st.selectbox("출력 언어", LANG_NAMES, index=LANG_NAMES.index(st.session_state.output_lang), key='output_select')

st.session_state.input_lang = input_lang
st.session_state.output_lang = output_lang

# 언어 전환 버튼
if st.button("언어 전환 (A ↔ B)"):
    temp = st.session_state.input_lang
    st.session_state.input_lang = st.session_state.output_lang
    st.session_state.output_lang = temp
    st.rerun()

# 실시간 마이크 녹음 (JS 컴포넌트 – 브라우저 마이크 직접 사용)
st.write("🎤 마이크 버튼으로 말하세요 (5초 자동 녹음 후 처리). 스마트폰에서 마이크 권한 허용하세요!")
if 'recorded_audio' not in st.session_state:
    st.session_state.recorded_audio = None

# JS로 마이크 녹음 (Web Audio API – 클라우드 호환)
mic_js = """
<div id="mic-div">
    <button id="mic-btn" onclick="toggleMic()">🎤 말하기 시작</button>
    <p id="status">준비 중... (마이크 허용 후 클릭)</p>
</div>
<script>
let isRecording = false;
let mediaRecorder;
let audioChunks = [];

async function toggleMic() {
    const status = document.getElementById('status');
    const btn = document.getElementById('mic-btn');
    if (!isRecording) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            isRecording = true;
            btn.innerHTML = '⏹️ 중지';
            status.textContent = '녹음 중... (5초 후 자동 처리)';
            
            mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                const reader = new FileReader();
                reader.readAsDataURL(audioBlob);
                reader.onloadend = () => {
                    // Streamlit 세션에 데이터 저장
                    parent.window.streamlitSetComponentValue({audio: reader.result});
                };
                stream.getTracks().forEach(track => track.stop());
            };
            mediaRecorder.start();
            setTimeout(() => {
                if (isRecording) mediaRecorder.stop();
            }, 5000);  # 5초 자동 중지
        } catch (err) {
            status.textContent = '마이크 오류: ' + err.message;
        }
    } else {
        mediaRecorder.stop();
        isRecording = false;
        btn.innerHTML = '🎤 말하기 시작';
        status.textContent = '처리 중...';
    }
}
</script>
"""

# Streamlit 컴포넌트로 JS 임베드
st.components.v1.html(mic_js, height=100)

# 녹음 데이터 처리 (JS에서 전송된 오디오)
recorded_audio = st.session_state.get('recorded_audio')
if recorded_audio and 'audio' in recorded_audio:
    audio_base64 = recorded_audio['audio']
    # Base64를 바이너리로 변환
    audio_bytes = base64.b64decode(audio_base64.split(',')[1])
    
    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
        tmp_file.write(audio_bytes)
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
        
        # TTS: 텍스트 → 음성 출력 (여성-like, 친근)
        tts = gTTS(translated_text, lang=LANGUAGES[output_lang], slow=False)
        audio_file = io.BytesIO()
        tts.write_to_fp(audio_file)
        audio_file.seek(0)
        st.audio(audio_file, format='audio/mp3')
        st.success("동시 통역 완료! (말하면 자동 처리됐어요.)")
    
    st.session_state.recorded_audio = None

# 파일 업로드 대안 (임시 – 들여쓰기 완벽 고침)
uploaded_file = st.file_uploader("파일 업로드 (대안)", type=['wav', 'mp3', 'm4a'])
if uploaded_file is not None:
    st.write("파일 업로드됐어요! 처리 중...")
    
    # 임시 파일 저장
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
        
        # TTS: 텍스트 → 음성 출력
        tts = gTTS(translated_text, lang=LANGUAGES[output_lang], slow=False)
        audio_file = io.BytesIO()
        tts.write_to_fp(audio_file)
        audio_file.seek(0)
        st.audio(audio_file, format='audio/mp3')
        st.info("TTS: gTTS (또렷한 여성-like 목소리). 업로드 파일로 테스트하세요!")

st.write("동시 통역 팁: 마이크 버튼 클릭 후 말하세요. 스마트폰에서 잘 동작해요 – 외부에서도 데이터로 OK!")
