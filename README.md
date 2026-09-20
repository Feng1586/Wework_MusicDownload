# MusicDL 企业微信音乐下载机器人

基于企业微信的音乐下载机器人，支持通过企业微信接口搜索和下载音乐。

## 功能特性

- 🎵 支持多平台音乐搜索和下载（QQ音乐、网易云音乐、咪咕音乐、酷我音乐、千千音乐）
- 💬 企业微信集成，通过聊天界面搜索和下载音乐
- 🔒 企业微信消息加密支持
- 🔄 消息去重机制，防止重复处理
- 📝 完善的日志系统
- ⚙️ 灵活的配置管理

## 项目结构

```
musicdl/
├── config/                 # 配置文件
│   ├── config.py          # 主配置文件（需自行配置）
│   └── config.example.py  # 配置示例文件
├── model/                 # 数据模型
│   └── wechat_url_valdator.py  # 企业微信消息验证
├── router/                # 路由处理
│   └── wechat_verify.py   # 企业微信回调路由
├── schemas/               # 数据结构
│   └── models.py          # Pydantic 模型
├── task/                  # 任务处理
│   ├── task.py            # 消息分发：搜索 / 下载入队 / 指令
│   └── download_queue.py  # 下载队列（后台 worker，逐首下载并推送进度）
├── utils/                 # 工具函数
│   ├── logger.py          # 日志系统
│   ├── notice.py          # 启动广播文案
│   └── version.py         # 版本号唯一来源
├── weworkapi/             # 企业微信 SDK
├── main.py                # 应用入口
├── requirements.txt       # 依赖包
└── README.md             # 项目说明
```

## 快速开始

### 1. 环境要求

- Python 3.7+
- 企业微信应用

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置

所有企业微信凭据都通过**环境变量**读取，代码和示例文件里都不含任何默认凭据。

复制环境变量示例并填写（推荐，Docker 与本地运行都适用）：

```bash
cp .env.example .env
```

```ini
# .env —— 变量名必须与 config/config.py 中 os.environ.get(...) 读的名字一致
STOKEN=your_token_here
S_ENCODING_AES_KEY=your_encoding_aes_key_here
S_CORP_ID=your_corp_id_here
AGENT_ID=your_agent_id_here
SECRET=your_secret_here
WECHAT_PROXY=http://your-proxy-or-qyapi/
```

| 变量 | 说明 |
|------|------|
| `STOKEN` | 企业微信应用的 Token |
| `S_ENCODING_AES_KEY` | 消息加密密钥 |
| `S_CORP_ID` | 企业 ID |
| `AGENT_ID` | 应用 ID |
| `SECRET` | 应用 Secret |
| `WECHAT_PROXY` | 企业微信 API 接入地址（结尾必须带 `/`） |

如果你不用 `.env`，也可以直接复制配置文件再手工填写：

```bash
cp config/config.example.py config/config.py
```

`config/config.py` 同样是环境变量优先的，把 `os.environ.get('STOKEN', "")` 的
第二个参数填成你的值即可。本机运行 `python main.py` 时走的就是这个文件。

> 注意：**不要**把填好的 `config/config.py` 或 `.env` 提交到仓库 ——
> 两者都已在 `.gitignore` 中，且 `.dockerignore` 也会把它们挡在镜像之外。

### 4. 配置企业微信回调

在企业微信管理后台配置应用回调URL：

- 回调URL: `http://your-server-ip:8000/wechat/callback`
- Token: 与 `.env` 中的 `STOKEN` 一致
- EncodingAESKey: 与 `.env` 中的 `S_ENCODING_AES_KEY` 一致

### 5. 启动服务

```bash
python main.py
```

服务将在 `http://0.0.0.0:8000` 启动（可用环境变量 `HOST` / `PORT` 覆盖）。

## Docker 部署

### 1. 使用 Dockerfile 构建镜像

```bash
# 构建镜像
docker build -t musicdl .

# 运行容器
docker run -d \
  --name musicdl \
  -p 8000:8000 \
  -v ./downloads:/app/downloads \
  -v ./config/config.py:/app/config/config.py:ro \
  musicdl
```

### 2. 使用 Docker Compose

先在当前目录创建 `.env` 文件（compose 会从它读取变量）：

```bash
cp .env.example .env
```

```ini
# .env 文件
STOKEN=your_token_here
S_ENCODING_AES_KEY=your_encoding_aes_key_here
S_CORP_ID=your_corp_id_here
AGENT_ID=your_agent_id_here
SECRET=your_secret_here
WECHAT_PROXY=http://your-proxy-or-qyapi/
```

启动服务：

```bash
docker compose up -d
```

> `docker-compose.yml` 里这几个变量用的是 `${VAR:?}` 形式：**缺少 `.env` 或漏填时会直接报错退出**，
> 而不是拿空凭据静默启动、到用户发消息时才报一句看不懂的「微信验证失败」。
> 若看到 `required variable ... is missing a value`，说明对应变量没填。

### 3. 配置文件挂载

Docker 容器支持通过环境变量覆盖配置文件中的企业微信参数，也可以通过挂载自定义配置：

```bash
# 挂载自定义配置
docker run -d \
  --name musicdl \
  -p 8000:8000 \
  -v ./config/config.py:/app/config/config.py:ro \
  -v ./downloads:/app/downloads \
  musicdl
```

## 使用方法

### 搜索音乐

在企业微信中发送歌曲名称，例如：

```
青花瓷
```

系统会返回搜索结果列表（编号从 1 开始，与代码里的 `id` 一致）：

```
1. 周杰伦, 青花瓷
2. 周杰伦, 青花瓷 (Live版)
3. 周杰伦, 青花瓷 (伴奏)
请回复最前面的数字ID进行下载
```

### 下载音乐

回复对应的数字ID，例如：

```
1
```

歌曲会**加入后台下载队列**，并立刻收到回执：

```
🎧 已加入下载队列：1
```

之后下载在后台按 FIFO 顺序进行，每首歌开始和结束都会收到通知：

```
⚙️ 开始下载：青花瓷-周杰伦
✅ 下载完成：青花瓷.flac
💾 大小：149.0 MB
```

**入队后不用等**：可以马上继续搜索下一首，队列里的歌会在后台慢慢下完。
下载失败时也会收到一条 `❌ 下载失败：歌名-歌手` 并附上原因。

### 批量下载

一次选多首，用逗号分隔（重复的编号会自动去重）：

```
1,3,5
```

只会收到一条汇总回执，然后按顺序一首一首下载：

```
🎧 已加入下载队列：1,3,5
```

## 技术栈

- **Web框架**: FastAPI
- **ASGI服务器**: Uvicorn
- **音乐下载**: musicdl
- **消息加密**: 企业微信官方 SDK
- **缓存**: cachetools
- **日志**: Python logging

## 注意事项

1. **企业微信代理**: 如果需要使用代理，请配置 `WeChatProxy` 参数
2. **VIP Cookies**: 某些平台需要 VIP 账号才能下载高质量音乐
3. **消息去重**: 系统内置 60 秒消息去重机制，防止重复处理
4. **下载目录**: 默认下载到 `downloads/` 目录

## 配置说明

### 企业微信配置

| 参数 | 说明 |
|------|------|
| `sToken` | 企业微信应用的 Token |
| `sEncodingAESKey` | 消息加密密钥 |
| `sCorpID` | 企业 ID |
| `AgentId` | 应用 ID |
| `Secret` | 应用 Secret |
| `WeChatProxy` | 企业微信 API 代理地址 |

### 音乐源配置

支持的音乐平台：

- `QQMusicClient`: QQ音乐
- `NeteaseMusicClient`: 网易云音乐
- `MiguMusicClient`: 咪咕音乐
- `KuwoMusicClient`: 酷我音乐
- `QianqianMusicClient`: 千千音乐

## 故障排查

### 消息重复发送

- 检查回调接口返回值是否为 `"success"` 字符串
- 确认消息去重缓存正常工作

### 下载失败

- 检查网络连接
- 确认音乐源配置正确
- 查看 API 请求日志

### 消息加密失败

- 检查 `sToken` 和 `sEncodingAESKey` 是否正确
- 确认企业微信后台配置与代码配置一致

## 许可证

本项目仅供学习和个人使用。

## 贡献

欢迎提交 Issue 和 Pull Request。

## 致谢

- [musicdl](https://github.com/CharlesPikachu/musicdl) - 音乐下载核心库
- 企业微信官方 SDK