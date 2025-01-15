import os
import time
import json
import re
import shutil
import markdown
import zipfile
import io
import requests
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
from markdown.extensions import fenced_code, tables, attr_list, def_list
from markdown.extensions import codehilite, footnotes, meta, toc
from markdown.extensions import nl2br, sane_lists, smarty, wikilinks
from urllib.parse import unquote, quote
from bs4 import BeautifulSoup
import pygments
from pygments import highlight
from pygments.lexers import get_lexer_for_filename, TextLexer
from pygments.formatters import HtmlFormatter

app = Flask(__name__)
app.secret_key = 'some_secret_key'

# 全局版本号
VERSION = "1.1.13"

# 定义支持预览的文件类型
PREVIEWABLE_EXTENSIONS = {
    # 文本文件
    '.txt': 'text',
    '.log': 'text',
    '.ini': 'text',
    '.conf': 'text',
    # Markdown文件
    '.md': 'markdown',
    # 代码文件
    '.py': 'code',
    '.js': 'code',
    '.html': 'code',
    '.css': 'code',
    '.java': 'code',
    '.cpp': 'code',
    '.c': 'code',
    '.h': 'code',
    '.hpp': 'code',
    '.json': 'code',
    '.xml': 'code',
    '.yaml': 'code',
    '.yml': 'code',
    '.sh': 'code',
    '.bat': 'code',
    '.ps1': 'code',
    '.sql': 'code',
    '.r': 'code',
    '.php': 'code',
    '.go': 'code',
    '.rb': 'code',
    '.rust': 'code',
    '.ts': 'code',
    '.jsx': 'code',
    '.tsx': 'code',
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'upload_folder')
METADATA_FILE = os.path.join(BASE_DIR, 'metadata.json')

# 留言数据文件路径
MESSAGES_FILE = os.path.join(BASE_DIR, 'messages.json')

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

def is_valid_name(filename):
    """
    验证文件名是否合法
    允许:
    - 中文字符
    - 英文字母
    - 数字
    - 常用标点符号和特殊字符
    禁止:
    - 文件系统的特殊字符 (/ \\ : * ? " < > |)
    - 以点(.)开头的文件名
    """
    # 禁止的字符
    forbidden_chars = r'[/\\:*?"<>|]'
    
    # 检查是否包含禁止的字符
    if re.search(forbidden_chars, filename):
        return False
    
    # 检查是否以点开头
    if filename.startswith('.'):
        return False
    
    # 检查长度
    if len(filename) == 0 or len(filename.encode('utf-8')) > 255:
        return False
    
    return True

def list_all_dirs():
    # 用 '/' 表示根目录
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

def render_markdown(content):
    # 配置Markdown扩展
    extensions = [
        'fenced_code',
        'tables',
        'attr_list',
        'def_list',
        'codehilite',
        'footnotes',
        'meta',
        'toc',
        'nl2br',
        'sane_lists',
        'smarty',
        'wikilinks'
    ]
    
    # 渲染Markdown
    md = markdown.Markdown(extensions=extensions)
    html_content = md.convert(content)
    
    # 生成大纲
    outline = []
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 为所有标题添加id和锚点
    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        level = int(heading.name[1])
        text = heading.get_text()
        
        # 生成锚点ID：保留中文和英文字母，其他字符替换为横线
        heading_id = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]+', '-', text)
        heading_id = re.sub(r'-+', '-', heading_id).strip('-')  # 合并多个横线并移除首尾横线
        
        # 确保ID唯一性
        if heading_id in [item['id'] for item in outline]:
            counter = 1
            while f"{heading_id}-{counter}" in [item['id'] for item in outline]:
                counter += 1
            heading_id = f"{heading_id}-{counter}"
        
        # 创建锚点元素
        anchor = soup.new_tag('a', href=f"#{heading_id}")
        anchor['class'] = 'header-anchor'
        anchor['id'] = heading_id
        heading['id'] = heading_id
        
        # 将原有内容包装在锚点中
        heading.wrap(anchor)
        
        outline.append({
            'level': level,
            'text': text,
            'id': heading_id
        })
    
    return str(soup), outline

# 添加一个辅助函数来处理路径
def normalize_path(path):
    """规范化路径，处理斜杠和编码问题"""
    if not path:
        return ''
    # 移除开头和结尾的斜杠
    path = path.strip('/')
    # 替换连续的斜杠为单个斜杠
    path = re.sub(r'/+', '/', path)
    # URL解码
    path = unquote(path)
    return path

def search_all_files(search_keyword):
    """搜索所有目录下的文件"""
    results = []
    metadata = load_metadata()
    
    # 遍历所有目录
    for root, dirs, files in os.walk(UPLOAD_FOLDER):
        # 获取相对路径
        rel_path = os.path.relpath(root, UPLOAD_FOLDER)
        rel_path = '' if rel_path == '.' else rel_path
        # 统一使用正斜杠
        rel_path = rel_path.replace('\\', '/')
        
        # 搜索文件夹
        for dir_name in dirs:
            if search_keyword.lower() in dir_name.lower():
                path = os.path.join(rel_path, dir_name) if rel_path else dir_name
                results.append({
                    'name': dir_name,
                    'path': path.replace('\\', '/'),
                    'is_folder': True
                })
        
        # 搜索文件
        for file_name in files:
            file_meta = metadata.get(file_name, {})
            original_name = file_meta.get('original_name', file_name)
            if search_keyword.lower() in original_name.lower():
                # 构建相对路径
                path = os.path.join(rel_path, file_name) if rel_path else file_name
                
                # 安全处理时间戳
                upload_time = file_meta.get('upload_time')
                edit_time = file_meta.get('edit_time')
                
                formatted_upload_time = format_timestamp(upload_time) if upload_time else ''
                formatted_edit_time = format_timestamp(edit_time) if edit_time else ''
                
                results.append({
                    'name': file_name,
                    'path': path.replace('\\', '/'),
                    'original_name': original_name,
                    'upload_time': formatted_upload_time,
                    'edit_time': formatted_edit_time,
                    'owner': file_meta.get('owner', 'shared'),
                    'extension': os.path.splitext(file_name)[1].lower(),
                    'is_folder': False
                })
    
    return results

# 定义友情链接
FRIEND_LINKS = sorted([
    {
        'url': 'http://10.75.48.202:5000/',
        'name': 'Timothy的点云生成平台'
    },
    {
        'url': 'http://10.75.49.47:5001/',
        'name': '材料费报销表生成器'
    },
    {
        'url': 'http://10.75.49.46:7006/',
        'name': 'Timothy的论文修改平台'
    },
    {
        'url': 'http://10.75.49.46:5002/',
        'name': 'Timothy的工作流'
    }
], key=lambda x: x['name'])

@app.route('/check_website_status')
def check_website_status():
    url = request.args.get('url')
    if not url:
        return jsonify({'status': 'error', 'message': 'URL is required'})
    
    try:
        # 设置更短的超时时间
        response = requests.get(url, timeout=1)
        return jsonify({'status': 'online' if response.status_code == 200 else 'offline'})
    except:
        return jsonify({'status': 'offline'})

def load_messages():
    if os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_messages(messages):
    with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=4)

@app.route('/messages', methods=['GET'])
def get_messages():
    messages = load_messages()
    # 移除 IP 地址信息再返回
    return jsonify([{k: v for k, v in msg.items() if k != 'ip_address'} for msg in messages])

@app.route('/messages', methods=['POST'])
def add_message():
    content = request.form.get('content', '').strip()
    username = request.form.get('username', '').strip()
    
    if not content:
        return jsonify({'status': 'error', 'message': '留言内容不能为空'})
    
    # 验证用户名不能包含"abyss"（不区分大小写）
    if username and ('abyss' in username.lower() or 'hhy' in username.lower()):
        return jsonify({'status': 'error', 'message': '说了别用我名字了哥'})
    
    # 规范化换行符
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    
    # 获取用户IP地址
    ip_address = request.remote_addr
    if request.headers.get('X-Forwarded-For'):
        ip_address = request.headers.get('X-Forwarded-For').split(',')[0]
    
    messages = load_messages()
    messages.append({
        'content': content,
        'username': username or '匿名用户',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'ip_address': ip_address  # 添加IP地址字段
    })
    
    # 只保留最近的50条留言
    if len(messages) > 50:
        messages = messages[-50:]
    
    save_messages(messages)
    return jsonify({'status': 'success'})

@app.route('/')
def welcome():
    messages = load_messages()
    return render_template('welcome.html', VERSION=VERSION, FRIEND_LINKS=FRIEND_LINKS, MESSAGES=messages)

@app.route('/home')
def index():
    current_dir = request.args.get('dir', '')
    sort_by = request.args.get('sort_by', 'name')
    sort_order = request.args.get('order', 'asc')
    search_keyword = request.args.get('search', '').strip()
    selected = request.args.get('selected', '')
    auth_user = request.args.get('auth_user', '').strip()

    # 处理路径中的特殊字符
    current_dir = normalize_path(current_dir)
    selected = normalize_path(selected) if selected else ''
    
    # 构建浏览路径
    browse_path = os.path.join(UPLOAD_FOLDER, current_dir) if current_dir else UPLOAD_FOLDER
    
    # 如果是文件路径，获取其目录
    if os.path.isfile(browse_path):
        browse_path = os.path.dirname(browse_path)
        current_dir = os.path.relpath(browse_path, UPLOAD_FOLDER)
    
    if not os.path.exists(browse_path):
        browse_path = UPLOAD_FOLDER
        current_dir = ''

    # 如果有搜索关键词，使用全局搜索
    if search_keyword:
        search_results = search_all_files(search_keyword)
        folders = [item for item in search_results if item['is_folder']]
        files = [item for item in search_results if not item['is_folder']]
    else:
        # 原有的目录浏览逻辑
        metadata = load_metadata()
        items = os.listdir(browse_path)
        folders = []
        files = []
        for item in items:
            full_path = os.path.join(browse_path, item)
            if os.path.isdir(full_path):
                folders.append(item)
            else:
                file_meta = metadata.get(item, {})
                original_name = file_meta.get('original_name', item)
                upload_time = file_meta.get('upload_time', '')
                edit_time = file_meta.get('edit_time', '')
                owner = file_meta.get('owner', 'shared')
                formatted_upload_time = format_timestamp(upload_time) if upload_time else ''
                formatted_edit_time = format_timestamp(edit_time) if edit_time else ''
                ext = os.path.splitext(item)[1].lower()
                
                files.append({
                    'name': item,
                    'original_name': original_name,
                    'upload_time': formatted_upload_time,
                    'edit_time': formatted_edit_time,
                    'owner': owner,
                    'extension': ext,
                    'path': current_dir
                })

    # 排序逻辑
    def sort_key(f):
        if sort_by == 'name':
            return f['original_name'].lower() if not isinstance(f, str) else f.lower()
        elif sort_by == 'upload_time':
            return f['upload_time'] if not isinstance(f, str) else ''
        elif sort_by == 'edit_time':
            return f['edit_time'] if not isinstance(f, str) else ''
        else:
            return f['original_name'].lower() if not isinstance(f, str) else f.lower()

    files = sorted(files, key=sort_key, reverse=(sort_order == 'desc'))

    parent_dir = ''
    if current_dir:
        parts = current_dir.strip('/').split('/')
        parent_dir = '/'.join(parts[:-1])

    selected_file_content = ''
    selected_file_owner = 'shared'
    selected_file_original_name = ''
    need_auth_to_view = False
    selected_file_html = ''
    is_new_file = (selected == '__new__')

    if selected and not is_new_file:
        selected_file_info = next((f for f in files if f['name'] == selected), None)
        if selected_file_info:
            if search_keyword:
                file_path = selected_file_info['path']
                browse_path = os.path.dirname(os.path.join(UPLOAD_FOLDER, file_path))
            else:
                file_path = selected
                browse_path = os.path.join(UPLOAD_FOLDER, current_dir)

            selected_file_path = os.path.normpath(os.path.join(browse_path, file_path))
            selected_file_owner = selected_file_info['owner']
            selected_file_original_name = selected_file_info['original_name']
            file_extension = selected_file_info['extension']

            # 检查文件是否支持预览
            if file_extension.lower() in PREVIEWABLE_EXTENSIONS:
                if selected_file_owner != 'shared':
                    if auth_user == selected_file_owner:
                        if os.path.exists(selected_file_path):
                            try:
                                with open(selected_file_path, 'r', encoding='utf-8') as f:
                                    selected_file_content = f.read()
                                selected_file_html, outline = render_file_content(selected_file_content, file_extension)
                            except Exception as e:
                                flash(f"读取文件失败: {str(e)}")
                                selected_file_content = ""
                                selected_file_html = ""
                                outline = []
                    else:
                        need_auth_to_view = True
                else:
                    if os.path.exists(selected_file_path):
                        try:
                            with open(selected_file_path, 'r', encoding='utf-8') as f:
                                selected_file_content = f.read()
                            selected_file_html, outline = render_file_content(selected_file_content, file_extension)
                        except Exception as e:
                            flash(f"读取文件失败: {str(e)}")
                            selected_file_content = ""
                            selected_file_html = ""
                            outline = []
            else:
                selected_file_html = "<p>此文件类型不支持预览</p>"
                outline = []

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
                           is_new_file=is_new_file,
                           outline=outline if 'outline' in locals() else [],
                           VERSION=VERSION)

@app.route('/create_new_file', methods=['POST'])
def create_new_file():
    current_dir = request.form.get('dir', '')
    new_name = request.form.get('new_filename', '').strip()
    owner_type = request.form.get('owner_type', 'shared')
    owner_user = request.form.get('owner_user', '').strip()

    if not new_name.lower().endswith('.md'):
        new_name += '.md'

    if not is_valid_name(new_name.replace('.md', '')):
        flash("文件名不合法，不能包含以下字符: / \\ : * ? \" < > | 且不能以.开头")
        return redirect(url_for('index', dir=current_dir))

    browse_path = os.path.join(UPLOAD_FOLDER, current_dir)
    if not os.path.exists(browse_path):
        os.makedirs(browse_path)
        
    file_path = os.path.join(browse_path, new_name)
    if os.path.exists(file_path):
        flash("已存在同名文件，无法新建")
        return redirect(url_for('index', dir=current_dir))

    # 创建空文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('')

    ts = str(int(time.time()))
    metadata = load_metadata()
    metadata[new_name] = {
        "original_name": new_name,
        "upload_time": ts,
        "edit_time": ts,
        "owner": owner_user if owner_type == 'personal' and owner_user else 'shared'
    }
    save_metadata(metadata)

    flash("新建文件成功")
    return redirect(url_for('index', dir=current_dir))

@app.route('/upload_file', methods=['POST'])
def upload_file():
    current_dir = request.form.get('dir', '').strip()
    owner_type = request.form.get('owner_type', 'shared')
    owner_user = request.form.get('owner_user', '').strip()
    
    if 'file' not in request.files:
        flash('没有选择文件')
        return redirect(url_for('index', dir=current_dir))
    
    files = request.files.getlist('file')
    if not files or all(file.filename == '' for file in files):
        flash('没有选择文件')
        return redirect(url_for('index', dir=current_dir))
    
    # 确保上传目录存在
    upload_path = os.path.join(UPLOAD_FOLDER, current_dir)
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)
    
    metadata = load_metadata()
    success_count = 0
    error_files = []
    
    for file in files:
        if file and file.filename:
            filename = file.filename
            
            # 检查文件名是否合法
            if not is_valid_name(filename):
                error_files.append(f"{filename} (文件名不能包含以下字符: / \\ : * ? \" < > | 且不能以.开头)")
                continue
            
            filepath = os.path.join(upload_path, filename)
            
            # 检查文件是否已存在
            if os.path.exists(filepath):
                error_files.append(f"{filename} (文件已存在)")
                continue
            
            try:
                file.save(filepath)
                metadata[filename] = {
                    'original_name': filename,
                    'upload_time': str(int(time.time())),
                    'edit_time': str(int(time.time())),
                    'owner': owner_user if owner_type == 'personal' else 'shared'
                }
                success_count += 1
            except Exception as e:
                error_files.append(f"{filename} (保存失败: {str(e)})")
    
    save_metadata(metadata)
    
    if success_count > 0:
        flash(f'成功上传 {success_count} 个文件')
    if error_files:
        flash('以下文件上传失败：\n' + '\n'.join(error_files))
    
    return redirect(url_for('index', dir=current_dir))

@app.route('/download/<path:filepath>')
def download_file(filepath):
    full_path = os.path.join(UPLOAD_FOLDER, filepath)
    if os.path.exists(full_path):
        # 检查是否是预览请求
        is_preview = request.args.get('preview', '').lower() == 'true'
        if is_preview:
            # 直接返回文件而不是下载
            return send_file(full_path)
        else:
            # 下载文件
            return send_file(full_path, as_attachment=True, download_name=os.path.basename(full_path))
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

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in selected_files:
            file_path = os.path.join(UPLOAD_FOLDER, dir_path, file)
            if os.path.isfile(file_path):
                zf.write(file_path, arcname=file)
    memory_file.seek(0)
    return send_file(memory_file, as_attachment=True, download_name='selected_files.zip')

@app.route('/delete_selected', methods=['POST'])
def delete_selected():
    selected_files = request.form.getlist('selected_files')
    current_dir = request.form.get('dir', '')
    owner_user = request.form.get('owner_user', '').strip()
    
    if not selected_files:
        flash("未选择任何文件")
        return redirect(url_for('index', dir=current_dir))
    
    metadata = load_metadata()
    success_count = 0
    error_files = []
    
    # 检查所有文件的权限
    for filename in selected_files:
        file_meta = metadata.get(filename, {})
        file_owner = file_meta.get('owner', 'shared')
        
        # 如果是个人文件，检查用户名
        if file_owner != 'shared' and file_owner != owner_user:
            error_files.append(f"{filename} (用户名验证失败)")
            continue
        
        file_path = os.path.join(UPLOAD_FOLDER, current_dir, filename)
        try:
            if os.path.exists(file_path) and os.path.isfile(file_path):
                os.remove(file_path)
                if filename in metadata:
                    del metadata[filename]
                success_count += 1
            else:
                error_files.append(f"{filename} (文件不存在)")
        except Exception as e:
            error_files.append(f"{filename} (删除失败: {str(e)})")
    
    # 保存更新后的元数据
    if success_count > 0:
        save_metadata(metadata)
        flash(f"成功删除 {success_count} 个文件")
    
    if error_files:
        flash('以下文件删除失败：\n' + '\n'.join(error_files))
    
    return redirect(url_for('index', dir=current_dir))

@app.route('/move_selected', methods=['POST'])
def move_selected():
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
    success_count = 0
    error_files = []

    for name in selected_files:
        source_path = os.path.join(UPLOAD_FOLDER, current_dir, name)
        if target_dir == '/':
            dest_path = os.path.join(UPLOAD_FOLDER, name)
        else:
            dest_path = os.path.join(UPLOAD_FOLDER, target_dir.strip('/'), name)

        if os.path.exists(dest_path):
            error_files.append(f"目标位置已存在同名文件 '{name}'")
            continue

        try:
            if os.path.exists(source_path) and os.path.isfile(source_path):
                shutil.move(source_path, dest_path)
                if name in metadata:
                    metadata[name]['upload_time'] = str(int(time.time()))
                    metadata[name]['edit_time'] = str(int(time.time()))
                success_count += 1
            else:
                error_files.append(f"文件 '{name}' 不存在或无法移动")
        except Exception as e:
            error_files.append(f"移动文件 '{name}' 失败: {str(e)}")

    if success_count > 0:
        save_metadata(metadata)
        flash(f"成功移动 {success_count} 个文件到 '{'根目录' if target_dir == '/' else target_dir}'")

    if error_files:
        flash('以下文件移动失败：\n' + '\n'.join(error_files))

    return redirect(url_for('index', dir=current_dir))

@app.route('/update_file', methods=['POST'])
def update_file():
    current_dir = request.form.get('dir', '')
    filename = request.form.get('filename', '')
    content = request.form.get('content', '')
    auth_user = request.form.get('auth_user', '')
    
    # 处理路径中的特殊字符
    current_dir = unquote(current_dir)
    filename = unquote(filename)
    
    # 构建文件路径
    file_path = os.path.join(UPLOAD_FOLDER, current_dir, filename)
    
    metadata = load_metadata()
    
    if not os.path.exists(file_path):
        flash(f"文件不存在: {filename}")
        return redirect(url_for('index', dir=current_dir))
    
    try:
        # 规范化换行符，移除多余的空行
        content = content.replace('\r\n', '\n').replace('\r', '\n')  # 统一换行符
        content = '\n'.join(line.rstrip() for line in content.splitlines())  # 移除每行末尾的空白字符
        
        with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)
        
        # 如果文件没有元数据，创建新的元数据
        if filename not in metadata:
            metadata[filename] = {
                'original_name': filename,
                'upload_time': str(int(time.time())),
                'owner': 'shared'
            }
        
        # 更新编辑时间
        metadata[filename]['edit_time'] = str(int(time.time()))
        save_metadata(metadata)
        flash("文件保存成功")
    except Exception as e:
        flash(f"保存失败: {str(e)}")
    
    return redirect(url_for('index', dir=current_dir, selected=filename, auth_user=auth_user))

@app.route('/delete_item/<path:filepath>', methods=['POST'])
def delete_item(filepath):
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
    current_dir = request.form.get('dir', '')
    folder_name = request.form.get('folder_name', '').strip()
    if folder_name:
        new_path = os.path.join(UPLOAD_FOLDER, current_dir, folder_name)
        if not os.path.exists(new_path):
            os.makedirs(new_path)
    return redirect(url_for('index', dir=current_dir))

@app.route('/rename_item', methods=['POST'])
def rename_item():
    current_dir = request.form.get('dir', '')
    old_name = request.form.get('old_name', '').strip()
    new_name = request.form.get('new_name', '').strip()
    item_type = request.form.get('type', '')

    # 处理文件重命名
    if item_type == 'file':
        # 保持原有扩展名
        extension = old_name[old_name.rfind('.'):]
        new_name = new_name + extension

    if not is_valid_name(new_name.replace('.md', '') if item_type == 'file' else new_name):
        flash("新名称不合法，只能包含字母、数字、下划线、点和横杠。")
        return redirect(url_for('index', dir=current_dir))

    old_path = os.path.join(UPLOAD_FOLDER, current_dir, old_name)
    new_path = os.path.join(UPLOAD_FOLDER, current_dir, new_name)

    if not os.path.exists(old_path):
        flash("原文件/文件夹不存在。")
        return redirect(url_for('index', dir=current_dir))

    if os.path.exists(new_path):
        flash("目标名称已存在，无法重命名。")
        return redirect(url_for('index', dir=current_dir))

    try:
        os.rename(old_path, new_path)
        if item_type == 'file':
            metadata = load_metadata()
            if old_name in metadata:
                file_meta = metadata[old_name]
                del metadata[old_name]
                file_meta['original_name'] = new_name
                file_meta['edit_time'] = str(int(time.time()))
                metadata[new_name] = file_meta
                save_metadata(metadata)
        flash(f"{'文件' if item_type == 'file' else '文件夹'}重命名成功。")
    except Exception as e:
        flash(f"重命名失败: {str(e)}")

    return redirect(url_for('index', dir=current_dir))

@app.route('/get_folder_contents/<path:folder_path>')
def get_folder_contents(folder_path):
    folder_full_path = os.path.join(UPLOAD_FOLDER, folder_path)
    if not os.path.exists(folder_full_path) or not os.path.isdir(folder_full_path):
        return jsonify({'error': '文件夹不存在'})
    
    metadata = load_metadata()
    contents = []
    personal_files = {}  # 用于统计个人文件的所有者
    
    for root, dirs, files in os.walk(folder_full_path):
        for file in files:
            file_extension = os.path.splitext(file)[1].lower()
            if file_extension in PREVIEWABLE_EXTENSIONS:
                file_meta = metadata.get(file, {})
                owner = file_meta.get('owner', 'shared')
                if owner != 'shared':
                    if owner not in personal_files:
                        personal_files[owner] = []
                    personal_files[owner].append(file)
                contents.append({
                    'name': file,
                    'owner': owner
                })
    
    return jsonify({
        'contents': contents,
        'personal_files': personal_files
    })

def render_file_content(content, file_extension):
    """根据文件类型渲染内容"""
    file_type = PREVIEWABLE_EXTENSIONS.get(file_extension.lower())
    
    if not file_type:
        return None, None  # 不支持的文件类型
        
    if file_type == 'markdown':
        return render_markdown(content)
    elif file_type in ['text', 'code']:
        try:
            if file_type == 'code':
                # 使用Pygments进行代码高亮
                lexer = get_lexer_for_filename(f"file{file_extension}")
            else:
                # 纯文本使用普通文本lexer
                lexer = TextLexer()
            
            formatter = HtmlFormatter(linenos=True, cssclass="highlight")
            highlighted_content = highlight(content, lexer, formatter)
            
            # 返回高亮后的HTML和空大纲（因为非markdown文件没有大纲）
            return highlighted_content, []
        except Exception as e:
            # 如果高亮失败，作为普通文本显示
            return f"<pre>{content}</pre>", []
    
    return None, None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
