from flask import Flask, render_template, request, jsonify, send_from_directory, session
from moviepy.editor import VideoFileClip, concatenate_videoclips
import os
import yt_dlp
from werkzeug.utils import secure_filename
import hashlib
from flask_socketio import SocketIO, emit
import eventlet
from datetime import datetime
import shutil
from datetime import timedelta

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, async_mode='eventlet')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_user_identifier():
    # 간단한 예시로 IP 주소를 해싱하여 고유 식별자로 사용
    user_ip = request.remote_addr
    return hashlib.md5(user_ip.encode()).hexdigest()

@app.context_processor
def inject_user_identifier():
    return dict(get_user_identifier=get_user_identifier)

@app.route('/youtube')
def index():
    user_id = get_user_identifier()
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)

    # 사용자 폴더 내의 파일 목록을 가져옴
    all_files = os.listdir(user_folder) if os.path.exists(user_folder) else []
    
    # regular_files, looped_files, combined_file로 나누기
    regular_files = [f for f in all_files if not f.startswith('looped_') and f != 'combined_video.mp4']
    looped_files = sorted([f for f in all_files if f.startswith('looped_')])
    combined_file = 'combined_video.mp4' if 'combined_video.mp4' in all_files else None

    return render_template('index.html', regular_files=regular_files, looped_files=looped_files, combined_file=combined_file)


@app.route('/download', methods=['POST'])
def download():
    url = request.form['url']
    user_id = get_user_identifier()
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
    
    # 고정된 파일명 사용
    video_filename = 'downloaded_video.mp4'
    video_filepath = os.path.join(user_folder, video_filename)

    # 기존 파일이 있으면 삭제
    if os.path.exists(video_filepath):
        os.remove(video_filepath)

    ydl_opts = {
        'outtmpl': video_filepath,
        'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]'
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            duration = info_dict.get('duration', 0)  # duration in seconds

            # Check if the video is longer than 20 minutes (1200 seconds)
            if duration > 1200:
                return jsonify({"error": "The video is longer than 20 minutes and cannot be downloaded."}), 400

            # Download the new file
            ydl.download([url])
            return jsonify({"success": "Video downloaded successfully."}), 200
    except Exception as e:
        print(f"Error downloading video: {e}")
        return jsonify({"error": "An error occurred while downloading the video."}), 500


@app.route('/uploads/<user_id>/<filename>')
def uploaded_file(user_id, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], user_id), filename)

@socketio.on('create_looped_video')
def create_looped_video(data):
    filename = data['filename']
    start_time = float(data['start_time'])
    end_time = float(data['end_time'])
    repeat_count = int(data['repeat_count'])

    user_id = get_user_identifier()
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
    video_filepath = os.path.join(user_folder, filename)

    try:
        clip = VideoFileClip(video_filepath).subclip(start_time, end_time)
        total_clips = repeat_count
        looped_clips = []

        # Check how many existing looped files there are
        existing_looped_files = [f for f in os.listdir(user_folder) if f.startswith("looped_")]
        if len(existing_looped_files) >= 5:
            socketio.emit('error', {'error': 'You have reached the maximum of 5 looped videos.'}, room=request.sid)
            return

        # Determine the new file number with current timestamp
        new_file_number = len(existing_looped_files) + 1
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f"looped_{new_file_number}_{timestamp}_{os.path.basename(filename)}"
        output_path = os.path.join(user_folder, output_filename)

        for i in range(total_clips):
            looped_clips.append(clip)
            progress = (i + 1) / total_clips * 100
            socketio.emit('progress', {'progress': progress}, room=request.sid)

        looped_clip = concatenate_videoclips(looped_clips)
        looped_clip.write_videofile(output_path, codec="libx264", audio_codec='aac')

        socketio.emit('complete', {'output_file': output_filename}, room=request.sid)
    except Exception as e:
        print(f"Error: {e}")
        socketio.emit('error', {'error': str(e)}, room=request.sid)

@app.route('/create_combined_video', methods=['POST'])
def create_combined_video():
    data = request.get_json()
    selected_files = data['selected_files']

    user_id = get_user_identifier()
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)

    try:
        clips = [VideoFileClip(os.path.join(user_folder, filename)) for filename in selected_files]
        combined_clip = concatenate_videoclips(clips)
        
        output_filename = "combined_video.mp4"
        output_path = os.path.join(user_folder, output_filename)
        combined_clip.write_videofile(output_path, codec="libx264", audio_codec='aac')

        return jsonify({'success': True, 'output_file': output_filename})

    except Exception as e:
        print(f"Error creating combined video: {e}")
        return jsonify({'success': False, 'error': str(e)})
    
import shutil

@app.route('/delete_video', methods=['POST'])
def delete_video():
    data = request.get_json()
    filename = data.get('filename')
    user_id = get_user_identifier()
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
    file_path = os.path.join(user_folder, filename)
    print(f"delete_video from file_path: {file_path}")

    try:
        if os.path.isfile(file_path):
            os.remove(file_path)
            return jsonify({'success': True}), 200
        elif os.path.isdir(file_path):
            return jsonify({'success': False, 'error': 'The path is a directory, not a file.'}), 400
        else:
            return jsonify({'success': False, 'error': 'File not found.'}), 404
    except PermissionError as e:
        print(f"Permission error deleting video: {e}")
        return jsonify({'success': False, 'error': 'Permission denied.'}), 500
    except Exception as e:
        print(f"Error deleting video: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
# @app.before_request
# def before_request():
#     print("before_request")
#     session.permanent = True
#     app.permanent_session_lifetime = timedelta(minutes=1)  # 세션 유효 시간 설정

@app.teardown_appcontext
def cleanup(exception=None):    
    print("cleanup")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)