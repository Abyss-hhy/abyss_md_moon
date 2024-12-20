# 1.安装Chocolatey（Windows 的包管理器）

PowerShell管理员

Set-ExecutionPolicy Bypass -Scope Process -Force; `
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; `
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

重开验证

choco --version



# 2.使用 Chocolatey 安装 Hugo

PowerShell管理员

choco install hugo -confirm（错误）

choco install hugo-extended -y（正确）

验证

hugo version



# 3.创建第一个 Hugo 网站

PowerShell管理员

存放目录

cd D:\abyss\project\MDstore

创建站点

hugo new site my-markdown-site

安装主题

导航到目录

cd my-markdown-site

添加主题

git init
git submodule add https://github.com/theNewDynamic/gohugo-theme-ananke.git themes/ananke

配置站点使用该主题

使用文本编辑器打开 `config.toml` 文件

theme = "ananke"

## 出错：没有config.toml文件（错误）

## 文件夹中有hugo.toml即可

Get-ChildItem -Force

### 方法一：重做

Remove-Item -Recurse -Force my-markdown-site

### 方法二：自己新建

New-Item -ItemType File -Name config.toml

baseURL = "http://example.org/"
languageCode = "zh-CN"
title = "我的 Markdown 网站"
theme = "ananke"

#### 说明：

`baseURL`：你的网站 URL，部署后需要更改为实际地址。

`languageCode`：语言代码，`zh-CN` 代表简体中文。

`title`：你的网站标题，可以根据需要修改。

`theme`：使用的主题，这里以 `ananke` 为例，你也可以选择其他主题。

#### 添加并配置主题

1.初始化 Git 仓库

git init

2.添加主题子模块

git submodule add https://github.com/theNewDynamic/gohugo-theme-ananke.git themes/ananke

3.在 `config.toml` 中指定主题

确认包含theme = "ananke"



# 4.启动 Hugo 本地服务器

cd D:\abyss\project\MDstore\my-markdown-site

hugo server -D

访问 http://localhost:1313/



