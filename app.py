from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import os
import time
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'some_secret_key'  # 用于flash消息，可自行修改

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'upload_folder')
METADATA_FILE = os.path.join(BASE_DIR, 'metadata.json')

# 初始化：确保upload_folder存在
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def load_metadata():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {}
    return data

def save_metadata(data):
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def format_timestamp(ts):
    return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')

@app.route('/')
def index():
    current_dir = request.args.get('dir', '')
    sort_by = request.args.get('sort_by', 'name')
    sort_order = request.args.get('order', 'asc')
    search_keyword = request.args.get('search', '').strip()
    selected = request.args.get('selected', '')

    browse_path = os.path.join(UPLOAD_FOLDER, current_dir)
    if not os.path.exists(browse_path):
        browse_path = UPLOAD_FOLDER
        current_dir = ''

    metadata = load_metadata()
    items = os.listdir(browse_path)
    folders = []
    files = []
    for item in items:
        full_path = os.path.join(browse_path, item)
        if os.path.isdir(full_path):
            folders.append(item)
        else:
            if item.lower().endswith('.md'):
                file_meta = metadata.get(item, {})
                original_name = file_meta.get('original_name', item)
                upload_time = file_meta.get('upload_time', '')
                edit_time = file_meta.get('edit_time', '')
                owner = file_meta.get('owner', 'shared')
                if search_keyword:
                    if search_keyword.lower() not in original_name.lower():
                        continue
                # 格式化时间
                formatted_upload_time = format_timestamp(upload_time) if upload_time else ''
                formatted_edit_time = format_timestamp(edit_time) if edit_time else ''
                files.append({
                    'name': item,
                    'original_name': original_name,
                    'upload_time': formatted_upload_time,
                    'edit_time': formatted_edit_time,
                    'owner': owner  # 仅用于后端验证，不在前端显示
                })

    # 排序
    def sort_key(f):
        if sort_by == 'name':
            return f['original_name'].lower()
        elif sort_by == 'upload_time':
            return f['upload_time']
        elif sort_by == 'edit_time':
            return f['edit_time']
        else:
            return f['original_name'].lower()

    files = sorted(files, key=sort_key, reverse=(sort_order == 'desc'))

    parent_dir = ''
    if current_dir:
        parts = current_dir.strip('/').split('/')
        parent_dir = '/'.join(parts[:-1])

    # 如果有选中的文件，读取其内容
    selected_file_content = ''
    selected_file_owner = 'shared'
    selected_file_original_name = ''
    if selected:
        selected_file_info = next((f for f in files if f['name'] == selected), None)
        if selected_file_info:
            selected_full_path = os.path.join(browse_path, selected)
            if os.path.exists(selected_full_path):
                with open(selected_full_path, 'r', encoding='utf-8') as f:
                    selected_file_content = f.read()
                selected_file_owner = selected_file_info['owner']
                selected_file_original_name = selected_file_info['original_name']

    return render_template('index.html',
                           current_dir=current_dir,
                           parent_dir=parent_dir,
                           folders=folders,
                           files=files,
                           sort_by=sort_by,
                           sort_order=sort_order,
                           search_keyword=search_keyword,
                           selected_file=selected,
                           selected_file_content=selected_file_content,
                           selected_file_owner=selected_file_owner,
                           selected_file_original_name=selected_file_original_name)

@app.route('/upload')
def upload_page():
    current_dir = request.args.get('dir', '')
    return render_template('upload.html', current_dir=current_dir)

@app.route('/upload_file', methods=['POST'])
def upload_file():
    current_dir = request.form.get('dir', '')
    browse_path = os.path.join(UPLOAD_FOLDER, current_dir)

    files = request.files.getlist('file')
    owner_type = request.form.get('owner_type', 'shared')
    owner_user = request.form.get('owner_user', '').strip()

    metadata = load_metadata()

    for file in files:
        if file:
            original_name = file.filename
            ts = str(int(time.time()))
            new_filename = f"{ts}_{original_name}"
            save_path = os.path.join(browse_path, new_filename)
            file.save(save_path)

            metadata[new_filename] = {
                "original_name": original_name,
                "upload_time": ts,
                "edit_time": ts,
                "owner": owner_user if owner_type == 'personal' and owner_user else 'shared'
            }

    save_metadata(metadata)
    return redirect(url_for('index', dir=current_dir))

@app.route('/download/<path:filepath>')
def download_file(filepath):
    full_path = os.path.join(UPLOAD_FOLDER, filepath)
    if os.path.exists(full_path):
        return send_file(full_path, as_attachment=True)
    else:
        flash("文件不存在")
        return redirect(url_for('index'))

@app.route('/update_file', methods=['POST'])
def update_file():
    current_dir = request.form.get('dir', '')
    filename = request.form.get('filename', '')
    owner_user_input = request.form.get('owner_user', '').strip()
    new_content = request.form.get('content', '')

    # 确定文件路径
    browse_path = os.path.join(UPLOAD_FOLDER, current_dir)
    full_path = os.path.join(browse_path, filename)

    if not os.path.exists(full_path):
        flash("文件不存在")
        return redirect(url_for('index', dir=current_dir))

    metadata = load_metadata()
    file_meta = metadata.get(filename, {})
    file_owner = file_meta.get('owner', 'shared')

    # 若为个人文件，需校验用户名
    if file_owner != 'shared':
        if owner_user_input != file_owner:
            flash("用户名不匹配，无权编辑此文件")
            return redirect(url_for('index', dir=current_dir, selected=filename))

    # 更新文件内容
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    # 更新编辑时间
    file_meta['edit_time'] = str(int(time.time()))
    metadata[filename] = file_meta
    save_metadata(metadata)

    flash("文件已保存")
    return redirect(url_for('index', dir=current_dir, selected=filename))

@app.route('/delete/<path:filepath>', methods=['POST'])
def delete_file(filepath):
    full_path = os.path.join(UPLOAD_FOLDER, filepath)
    metadata = load_metadata()
    file_meta = metadata.get(os.path.basename(filepath), {})

    user_input_owner = request.form.get('owner_user', '').strip()
    if file_meta.get('owner', 'shared') != 'shared':
        if user_input_owner != file_meta['owner']:
            flash("用户名不匹配，无权删除此文件")
            return redirect(url_for('index'))

    if os.path.exists(full_path) and os.path.isfile(full_path):
        os.remove(full_path)
        if os.path.basename(filepath) in metadata:
            del metadata[os.path.basename(filepath)]
            save_metadata(metadata)
        flash("文件已删除")
    else:
        flash("文件不存在或无法删除")

    return redirect(url_for('index', dir=os.path.dirname(filepath)))

@app.route('/mkdir', methods=['POST'])
def mkdir():
    current_dir = request.form.get('dir', '')
    folder_name = request.form.get('folder_name', '').strip()
    if folder_name:
        new_path = os.path.join(UPLOAD_FOLDER, current_dir, folder_name)
        if not os.path.exists(new_path):
            os.makedirs(new_path)
    return redirect(url_for('index', dir=current_dir))

@app.route('/rmdir', methods=['POST'])
def rmdir():
    current_dir = request.form.get('dir', '')
    folder_name = request.form.get('folder_name', '').strip()
    if folder_name:
        target_path = os.path.join(UPLOAD_FOLDER, current_dir, folder_name)
        if os.path.exists(target_path) and os.path.isdir(target_path) and not os.listdir(target_path):
            os.rmdir(target_path)
        else:
            flash("文件夹非空或不存在，无法删除")
    return redirect(url_for('index', dir=current_dir))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
