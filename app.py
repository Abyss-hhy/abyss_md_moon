import os
import time
import json
import re
import shutil
import markdown
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, flash

app = Flask(__name__)
app.secret_key = 'some_secret_key'  # 可自行修改

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'upload_folder')
METADATA_FILE = os.path.join(BASE_DIR, 'metadata.json')

# 确保 upload_folder 存在
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def load_metadata():
    """加载 metadata.json 中的记录"""
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {}
    return data

def save_metadata(data):
    """保存记录到 metadata.json"""
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def format_timestamp(ts):
    """将时间戳转成年月日时分秒字符串"""
    return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')

def is_valid_name(name):
    """
    检验文件名只允许: 字母、数字、下划线、点、横杠
    不允许中文或其他特殊字符
    """
    pattern = re.compile(r'^[A-Za-z0-9._-]+$')
    return bool(pattern.match(name))

def list_all_dirs():
    """
    遍历 upload_folder 下的所有子目录，用 '/' 表示根目录
    """
    dir_set = set()
    for root, dirs, files in os.walk(UPLOAD_FOLDER):
        rel_path = os.path.relpath(root, UPLOAD_FOLDER)
        if rel_path == '.':
            dir_set.add('/')
        else:
            d_path = rel_path.replace('\\', '/')
            dir_set.add(d_path)
            for d in dirs:
                sub_path = os.path.join(d_path, d).replace('\\', '/')
                dir_set.add(sub_path)
    dir_list = list(dir_set)
    dir_list.sort()
    return dir_list

@app.route('/')
def index():
    """
    主页面
    """
    current_dir = request.args.get('dir', '')
    sort_by = request.args.get('sort_by', 'name')
    sort_order = request.args.get('order', 'asc')
    search_keyword = request.args.get('search', '').strip()
    selected = request.args.get('selected', '')
    auth_user = request.args.get('auth_user', '').strip()

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
            # 文件夹
            if search_keyword:
                if search_keyword.lower() not in item.lower():
                    continue
            folders.append(item)
        else:
            # 只处理 .md 文件
            if item.lower().endswith('.md'):
                file_meta = metadata.get(item, {})
                original_name = file_meta.get('original_name', item)
                upload_time = file_meta.get('upload_time', '')
                edit_time = file_meta.get('edit_time', '')
                owner = file_meta.get('owner', 'shared')
                if search_keyword:
                    if search_keyword.lower() not in original_name.lower():
                        continue
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

    # 计算父目录
    parent_dir = ''
    if current_dir:
        parts = current_dir.strip('/').split('/')
        parent_dir = '/'.join(parts[:-1])

    selected_file_content = ''
    selected_file_owner = 'shared'
    selected_file_original_name = ''
    need_auth_to_view = False
    selected_file_html = ''
    # 是否新建文件
    is_new_file = (selected == '__new__')

    # 如果是已有文件
    if selected and not is_new_file:
        selected_file_info = next((f for f in files if f['name'] == selected), None)
        if selected_file_info:
            selected_full_path = os.path.join(browse_path, selected)
            selected_file_owner = selected_file_info['owner']
            selected_file_original_name = selected_file_info['original_name']

            if selected_file_owner != 'shared':
                # 个人文件需用户名匹配
                if auth_user == selected_file_owner:
                    if os.path.exists(selected_full_path):
                        with open(selected_full_path, 'r', encoding='utf-8') as f:
                            selected_file_content = f.read()
                        selected_file_html = markdown.markdown(selected_file_content)
                else:
                    need_auth_to_view = True
            else:
                # 共享文件
                if os.path.exists(selected_full_path):
                    with open(selected_full_path, 'r', encoding='utf-8') as f:
                        selected_file_content = f.read()
                    selected_file_html = markdown.markdown(selected_file_content)

    all_dirs = list_all_dirs()

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
                           need_auth_to_view=need_auth_to_view,
                           selected_file_html=selected_file_html,
                           all_dirs=all_dirs,
                           is_new_file=is_new_file)

@app.route('/create_new_file', methods=['POST'])
def create_new_file():
    """保存新建 MD 文件"""
    current_dir = request.form.get('dir', '')
    new_name = request.form.get('new_filename', '').strip()
    owner_type = request.form.get('owner_type', 'shared')
    owner_user = request.form.get('owner_user', '').strip()
    content = request.form.get('content', '')

    if not new_name.lower().endswith('.md'):
        new_name += '.md'

    if not is_valid_name(new_name.replace('.md', '')):
        flash("文件名不合法，只能包含字母、数字、下划线、点和横杠")
        return redirect(url_for('index', dir=current_dir, selected='__new__'))

    browse_path = os.path.join(UPLOAD_FOLDER, current_dir)
    file_path = os.path.join(browse_path, new_name)

    if os.path.exists(file_path):
        flash("已存在同名文件，无法新建")
        return redirect(url_for('index', dir=current_dir, selected='__new__'))

    # 创建并写入内容
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    ts = str(int(time.time()))
    metadata = load_metadata()
    metadata[new_name] = {
        "original_name": new_name,
        "upload_time": ts,
        "edit_time": ts,
        "owner": owner_user if owner_type=='personal' and owner_user else 'shared'
    }
    save_metadata(metadata)

    flash("新建文件成功")
    return redirect(url_for('index', dir=current_dir, selected=new_name))

@app.route('/upload')
def upload_page():
    """上传文件页面"""
    current_dir = request.args.get('dir', '')
    return render_template('upload.html', current_dir=current_dir)

@app.route('/upload_file', methods=['POST'])
def upload_file():
    """处理用户上传文件"""
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
    """单个文件下载"""
    full_path = os.path.join(UPLOAD_FOLDER, filepath)
    if os.path.exists(full_path):
        return send_file(full_path, download_name='selected_files.zip', as_attachment=True)
    else:
        flash("文件不存在")
        return redirect(url_for('index'))

@app.route('/download_selected', methods=['POST'])
def download_selected():
    """批量下载所选文件"""
    selected_files = request.form.getlist('selected_files')
    dir_path = request.form.get('dir', '')

    if not selected_files:
        flash("未选择任何文件进行下载。")
        return redirect(url_for('index', dir=dir_path))

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in selected_files:
            file_path = os.path.join(UPLOAD_FOLDER, dir_path, file)
            if os.path.isfile(file_path) and file.lower().endswith('.md'):
                zf.write(file_path, arcname=file)
    memory_file.seek(0)
    return send_file(memory_file, download_name='selected_files.zip', as_attachment=True)

@app.route('/delete_selected', methods=['POST'])
def delete_selected():
    """批量删除所选文件或文件夹"""
    selected_files = request.form.getlist('selected_files')
    dir_path = request.form.get('dir', '')
    owner_user = request.form.get('owner_user', '').strip()

    if not selected_files:
        flash("未选择任何文件或文件夹进行删除。")
        return redirect(url_for('index', dir=dir_path))

    metadata = load_metadata()
    for name in selected_files:
        target_path = os.path.join(UPLOAD_FOLDER, dir_path, name)
        if os.path.isdir(target_path):
            # 文件夹
            if os.path.exists(target_path):
                shutil.rmtree(target_path)
                flash(f"文件夹 '{name}' 已删除。")
            else:
                flash(f"文件夹 '{name}' 不存在或无法删除。")
        else:
            # 文件
            file_meta = metadata.get(name, {})
            file_owner = file_meta.get('owner', 'shared')
            if file_owner != 'shared' and owner_user != file_owner:
                flash(f"文件 '{file_meta.get('original_name', name)}' 的用户名不匹配，无法删除。")
                continue
            if os.path.exists(target_path) and os.path.isfile(target_path):
                os.remove(target_path)
                if name in metadata:
                    del metadata[name]
                flash(f"文件 '{file_meta.get('original_name', name)}' 已删除。")
            else:
                flash(f"文件 '{file_meta.get('original_name', name)}' 不存在或无法删除。")

    save_metadata(metadata)
    return redirect(url_for('index', dir=dir_path))

@app.route('/move_selected', methods=['POST'])
def move_selected():
    """批量移动所选文件或文件夹"""
    selected_files = request.form.getlist('selected_files')
    target_dir = request.form.get('target_dir', None)
    current_dir = request.form.get('dir', '').strip()

    if not selected_files:
        flash("未选择任何文件进行移动。")
        return redirect(url_for('index', dir=current_dir))

    if target_dir is None:
        flash("未选择目标目录。")
        return redirect(url_for('index', dir=current_dir))

    metadata = load_metadata()
    for name in selected_files:
        source_path = os.path.join(UPLOAD_FOLDER, current_dir, name)
        if target_dir == '/':
            dest_path = os.path.join(UPLOAD_FOLDER, name)
        else:
            dest_path = os.path.join(UPLOAD_FOLDER, target_dir.strip('/'), name)

        if os.path.exists(dest_path):
            flash(f"目标位置已存在同名文件或文件夹 '{name}'，无法移动。")
            continue

        if os.path.isdir(source_path):
            shutil.move(source_path, dest_path)
            flash(f"文件夹 '{name}' 已移动到 '{'根目录' if target_dir == '/' else target_dir}'。")
        else:
            if name not in metadata:
                flash(f"元数据中未找到文件 '{name}'，无法移动。")
                continue
            file_owner = metadata[name].get('owner', 'shared')
            if file_owner != 'shared':
                flash(f"文件 '{metadata[name].get('original_name', name)}' 是个人文件，无法批量移动。")
                continue
            if os.path.exists(source_path) and os.path.isfile(source_path):
                shutil.move(source_path, dest_path)
                metadata[name]['upload_time'] = str(int(time.time()))
                metadata[name]['edit_time'] = str(int(time.time()))
                flash(f"文件 '{metadata[name].get('original_name', name)}' 已移动到 '{'根目录' if target_dir == '/' else target_dir}'。")
            else:
                flash(f"文件 '{metadata[name].get('original_name', name)}' 不存在或无法移动。")

    save_metadata(metadata)
    return redirect(url_for('index', dir=current_dir))

@app.route('/update_file', methods=['POST'])
def update_file():
    """更新已有 MD 文件内容"""
    current_dir = request.form.get('dir', '')
    filename = request.form.get('filename', '')
    owner_user_input = request.form.get('owner_user', '').strip()
    new_content = request.form.get('content', '')

    browse_path = os.path.join(UPLOAD_FOLDER, current_dir)
    full_path = os.path.join(browse_path, filename)

    if not os.path.exists(full_path):
        flash("文件不存在")
        return redirect(url_for('index', dir=current_dir))

    metadata = load_metadata()
    file_meta = metadata.get(filename, {})
    file_owner = file_meta.get('owner', 'shared')

    if file_owner != 'shared':
        if owner_user_input != file_owner:
            flash("用户名不匹配，无权编辑此文件")
            return redirect(url_for('index', dir=current_dir, selected=filename))

    # 写入新内容
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    file_meta['edit_time'] = str(int(time.time()))
    metadata[filename] = file_meta
    save_metadata(metadata)

    flash("文件已保存")
    return redirect(url_for('index', dir=current_dir, selected=filename, auth_user=owner_user_input if file_owner!='shared' else ''))

@app.route('/delete_item/<path:filepath>', methods=['POST'])
def delete_item(filepath):
    """单个文件或文件夹删除"""
    full_path = os.path.join(UPLOAD_FOLDER, filepath)
    if os.path.isdir(full_path):
        if os.path.exists(full_path):
            shutil.rmtree(full_path)
            flash(f"文件夹 '{os.path.basename(filepath)}' 已删除。")
        else:
            flash("文件夹不存在或无法删除")
    else:
        metadata = load_metadata()
        file_meta = metadata.get(os.path.basename(filepath), {})
        file_owner = file_meta.get('owner', 'shared')
        user_input_owner = request.form.get('owner_user', '').strip()
        if file_owner != 'shared' and user_input_owner != file_owner:
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
    """新建文件夹"""
    current_dir = request.form.get('dir', '')
    folder_name = request.form.get('folder_name', '').strip()
    if folder_name:
        new_path = os.path.join(UPLOAD_FOLDER, current_dir, folder_name)
        if not os.path.exists(new_path):
            os.makedirs(new_path)
    return redirect(url_for('index', dir=current_dir))

@app.route('/rename_item', methods=['POST'])
def rename_item():
    """重命名文件或文件夹"""
    current_dir = request.form.get('dir', '')
    old_name = request.form.get('old_name', '').strip()
    new_name = request.form.get('new_name', '').strip()
    item_type = request.form.get('type', '')

    if not is_valid_name(new_name.replace('.md','')) and item_type=='file':
        flash("文件名不合法，只能包含字母、数字、下划线、点和横杠。")
        return redirect(url_for('index', dir=current_dir))

    if item_type == 'file' and not new_name.lower().endswith('.md'):
        new_name += '.md'

    old_path = os.path.join(UPLOAD_FOLDER, current_dir, old_name)
    new_path = os.path.join(UPLOAD_FOLDER, current_dir, new_name)

    if not os.path.exists(old_path):
        flash("原文件/文件夹不存在。")
        return redirect(url_for('index', dir=current_dir))

    if os.path.exists(new_path):
        flash("目标名称已存在，无法重命名。")
        return redirect(url_for('index', dir=current_dir))

    if item_type == 'file':
        metadata = load_metadata()
        if old_name not in metadata:
            flash("元数据中未找到此文件。")
            return redirect(url_for('index', dir=current_dir))
        os.rename(old_path, new_path)
        file_meta = metadata[old_name]
        del metadata[old_name]
        file_meta['original_name'] = new_name
        file_meta['edit_time'] = str(int(time.time()))
        metadata[new_name] = file_meta
        save_metadata(metadata)
        flash("文件重命名成功。")
    elif item_type == 'folder':
        os.rename(old_path, new_path)
        flash("文件夹重命名成功。")
    else:
        flash("无效的重命名类型。")

    return redirect(url_for('index', dir=current_dir))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
