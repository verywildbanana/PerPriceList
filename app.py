from flask import Flask, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
import pandas as pd
import time
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres.vsgfnpxuelgppyjbxpqr:veryWild$521@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres'
db = SQLAlchemy(app)

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


class product_list(db.Model):
    id = db.Column(db.BigInteger, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    product_id = db.Column(db.String, nullable=True)
    product_text = db.Column(db.String, nullable=True)
    product_price = db.Column(db.BigInteger, nullable=True)
    product_per_price = db.Column(db.Float, nullable=True)
    link = db.Column(db.String, nullable=True)
    product_tag = db.Column(db.String, nullable=True)

    def __init__(self, created_at, product_id, product_text, product_price, product_per_price, link, product_tag):
        self.created_at = created_at
        self.product_id = product_id
        self.product_text = product_text
        self.product_price = product_price
        self.product_per_price = product_per_price
        self.link = link
        self.product_tag = product_tag


@app.route('/products', methods=['GET'])
def get_products():
    try:
        # 모든 데이터 가져오기
        products = product_list.query.all()
        result = [
            {
                "id": product.id,
                "created_at": product.created_at,
                "product_id": product.product_id,
                "product_text": product.product_text,
                "product_price": product.product_price,
                "product_per_price": product.product_per_price,
                "link": product.link,
                "product_tag": product.product_tag
            }
            for product in products
        ]
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": "Failed to fetch data", "error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)