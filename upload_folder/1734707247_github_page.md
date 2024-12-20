创建账户

检查安装

git --version

### 创建一个新的 GitHub 仓库

1. **登录 GitHub**。

2. **点击右上角的 `+` 按钮**，选择 **`New repository`**。

3. 填写仓库信息

   ：

   - **Repository name（仓库名称）**：例如 `my-markdown-site`。
   - **Description（描述）**：可选，例如 `用于存放和预览 Markdown 文件的网站`。
   - **Public（公开）或 Private（私有）**：根据需要选择，建议选择 `Public`。
   - **勾选** `Initialize this repository with a README` 选项 **不要勾选**，因为我们将从本地推送现有项目。

4. **点击** `Create repository`。

   

初始化 Git 仓库（如果尚未初始化）

cd D:\abyss\project\MDstore\my-markdown-site

git init

添加远程仓库

git remote add origin https://github.com/Abyss.H/my-markdown-site.git

添加所有文件并提交

git add .
git commit -m "Initial commit"
