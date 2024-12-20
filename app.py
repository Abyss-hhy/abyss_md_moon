from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import os
import time
import json
from datetime import datetime
import zipfile
import io

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
    auth_user = request.args.get('auth_user', '').strip()  # 用户输入查看文件的用户名

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
                    'owner': owner
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

    # 选中文件逻辑
    selected_file_content = ''
    selected_file_owner = 'shared'
    selected_file_original_name = ''
    need_auth_to_view = False  # 标记是否需要输入用户名才能查看
    if selected:
        selected_file_info = next((f for f in files if f['name'] == selected), None)
        if selected_file_info:
            selected_full_path = os.path.join(browse_path, selected)
            selected_file_owner = selected_file_info['owner']
            selected_file_original_name = selected_file_info['original_name']

            if selected_file_owner != 'shared':
                # 是个人文件，需要auth_user匹配
                if auth_user == selected_file_owner:
                    # 用户名匹配，显示内容
                    if os.path.exists(selected_full_path):
                        with open(selected_full_path, 'r', encoding='utf-8') as f:
                            selected_file_content = f.read()
                else:
                    # 用户名不匹配或者未提供
                    need_auth_to_view = True
            else:
                # 共享文件，无需用户名
                if os.path.exists(selected_full_path):
                    with open(selected_full_path, 'r', encoding='utf-8') as f:
                        selected_file_content = f.read()

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
                           selected_file_original_name=selected_file_original_name,
                           need_auth_to_view=need_auth_to_view)

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

@app.route('/download_selected', methods=['POST'])
def download_selected():
    selected_files = request.form.getlist('selected_files')
    dir_path = request.form.get('dir', '')

    if not selected_files:
        flash("未选择任何文件进行下载。")
        return redirect(url_for('index', dir=dir_path))

    # 创建内存中的ZIP文件
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in selected_files:
            file_path = os.path.join(UPLOAD_FOLDER, dir_path, file)
            if os.path.exists(file_path) and file.lower().endswith('.md'):
                zf.write(file_path, arcname=file)

    memory_file.seek(0)
    return send_file(memory_file, attachment_filename='selected_files.zip', as_attachment=True)

@app.route('/delete_selected', methods=['POST'])
def delete_selected():
    selected_files = request.form.getlist('selected_files')
    dir_path = request.form.get('dir', '')
    owner_user = request.form.get('owner_user', '').strip()

    if not selected_files:
        flash("未选择任何文件进行删除。")
        return redirect(url_for('index', dir=dir_path))

    metadata = load_metadata()
    for file in selected_files:
        file_meta = metadata.get(file, {})
        file_owner = file_meta.get('owner', 'shared')
        if file_owner != 'shared' and owner_user != file_owner:
            flash(f"文件 '{file_meta.get('original_name', file)}' 的用户名不匹配，无法删除。")
            continue  # 跳过未通过验证的文件

        file_path = os.path.join(UPLOAD_FOLDER, dir_path, file)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            os.remove(file_path)
            del metadata[file]
            flash(f"文件 '{file_meta.get('original_name', file)}' 已删除。")
        else:
            flash(f"文件 '{file_meta.get('original_name', file)}' 不存在或无法删除。")

    save_metadata(metadata)
    return redirect(url_for('index', dir=dir_path))

@app.route('/move_selected', methods=['POST'])
def move_selected():
    selected_files = request.form.getlist('selected_files')
    target_dir = request.form.get('target_dir', '').strip()
    current_dir = request.form.get('dir', '').strip()

    if not selected_files:
        flash("未选择任何文件进行移动。")
        return redirect(url_for('index', dir=current_dir))

    if not target_dir:
        flash("目标目录不能为空。")
        return redirect(url_for('index', dir=current_dir))

    target_path = os.path.join(UPLOAD_FOLDER, target_dir)
    if not os.path.exists(target_path):
        os.makedirs(target_path)

    metadata = load_metadata()
    for file in selected_files:
        file_meta = metadata.get(file, {})
        file_owner = file_meta.get('owner', 'shared')
        file_path = os.path.join(UPLOAD_FOLDER, current_dir, file)
        dest_path = os.path.join(target_path, file)

        if file_owner != 'shared':
            flash(f"文件 '{file_meta.get('original_name', file)}' 是个人文件，无法批量移动。")
            continue  # 跳过个人文件的批量移动

        if os.path.exists(file_path) and os.path.isfile(file_path):
            os.rename(file_path, dest_path)
            metadata[file]['upload_time'] = str(int(time.time()))
            metadata[file]['edit_time'] = str(int(time.time()))
            flash(f"文件 '{file_meta.get('original_name', file)}' 已移动到 '{target_dir}'。")
        else:
            flash(f"文件 '{file_meta.get('original_name', file)}' 不存在或无法移动。")

    save_metadata(metadata)
    return redirect(url_for('index', dir=current_dir))

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
    return redirect(url_for('index', dir=current_dir, selected=filename, auth_user=owner_user_input if file_owner!='shared' else ''))

@app.route('/delete/<path:filepath>', methods=['POST'])
def delete_file(filepath):
    full_path = os.path.join(UPLOAD_FOLDER, filepath)
    metadata = load_metadata()
    file_meta = metadata.get(os.path.basename(filepath), {})

    user_input_owner = request.form.get('owner_user', '').strip()
    if file_meta.get('owner', 'shared') != 'shared':
        if user_input_owner != file_meta['owner']:
            flash("用户名不匹配，无权删除此文件")
            return redirect(url_for('index', dir=os.path.dirname(filepath)))

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
            flash(f"文件夹 '{folder_name}' 已删除。")
        else:
            flash("文件夹非空或不存在，无法删除")
    return redirect(url_for('index', dir=current_dir))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
