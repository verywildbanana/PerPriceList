from flask import Flask, request, render_template_string
from youtube_transcript_api import YouTubeTranscriptApi
import pandas as pd

app = Flask(__name__)

@app.route('/get')
def home():
    # URL에서 'name' 파라미터 추출
    id = request.args.get('id', 'World')
    start_time = float(request.args.get('start', 0))  # 시작 시간
    end_time = float(request.args.get('end', 0))  # 종료 시간
    transcript = get_transcript(id, start_time, end_time)
    return transcript

def get_transcript(video_id, start_time, end_time):
    # 전체 자막 가져오기
    transcript = YouTubeTranscriptApi.get_transcript(video_id)
    # 필터링된 자막 리스트
    # filtered_transcript = [entry for entry in transcript if start_time <= entry['start'] <= end_time]
    df = pd.DataFrame(transcript)
    df['interval'] = (df['start'] // 30).astype(int)

    # 각 그룹별로 텍스트를 HTML 형식으로 만들기
    grouped_text = df.groupby('interval')['text'].apply(lambda x: '<br>'.join(x)).reset_index()

    # HTML 내용 생성
    html_content = '<html><head><title>Subtitle Segments</title></head><body>'
    html_content += '<h1>Subtitle Text</h1>'

    for _, row in grouped_text.iterrows():
        html_content += f"<h2>Interval: {row['interval']*30}-{(row['interval']+1)*30} seconds</h2>"
        html_content += f"<p>{row['text']}</p>"

    html_content += '</body></html>'

    return html_content


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)