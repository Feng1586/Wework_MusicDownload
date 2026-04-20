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
│   └── task.py            # 音乐搜索和下载任务
├── utils/                 # 工具函数
│   └── logger.py          # 日志系统
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

复制配置示例文件并修改：

```bash
cp config/config.example.py config/config.py
```

编辑 `config/config.py`，填入你的企业微信配置：

```python
# 企业微信配置
sToken = "your_token_here"
sEncodingAESKey = "your_encoding_aes_key_here"
sCorpID = "your_corp_id_here"
AgentId = "your_agent_id_here"
Secret = "your_secret_here"
WeChatProxy = "https://qyapi.weixin.qq.com/"  # 或使用你的代理地址

# 音乐平台 VIP Cookies（可选）
QqVipCookies = ""
MiguVipCookies = ""
NeteaseVipCookies = ""
KuwoVipCookies = ""
QianqianVipCookies = ""

# 启用的音乐源
src_names = ['QQMusicClient']  # 可选: ['MiguMusicClient', 'NeteaseMusicClient', 'QQMusicClient', 'KuwoMusicClient', 'QianqianMusicClient']
```

### 4. 配置企业微信回调

在企业微信管理后台配置应用回调URL：

- 回调URL: `http://your-server-ip:8000/wechat/callback`
- Token: 与配置文件中的 `sToken` 一致
- EncodingAESKey: 与配置文件中的 `sEncodingAESKey` 一致

### 5. 启动服务

```bash
python main.py
```

服务将在 `http://0.0.0.0:8000` 启动。

<<<<<<< HEAD
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

创建 `.env` 文件配置企业微信参数：

```bash
# .env 文件
STOKEN=your_token_here
S_ENCODING_AES_KEY=your_encoding_aes_key_here
S_CORP_ID=your_corp_id_here
AGENT_ID=your_agent_id_here
SECRET=your_secret_here
WECHAT_PROXY=https://qyapi.weixin.qq.com/
```

启动服务：

```bash
docker-compose up -d
```

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

=======
>>>>>>> 1b6076f66c50fa4f06b2396277a63e0615d1a185
## 使用方法

### 搜索音乐

在企业微信中发送歌曲名称，例如：

```
青花瓷
```

系统会返回搜索结果列表：

```
0. 周杰伦, 青花瓷
1. 周杰伦, 青花瓷 (Live版)
2. 周杰伦, 青花瓷 (伴奏)
请回复最前面的数字ID进行下载
```

### 下载音乐

回复对应的数字ID，例如：

```
0
```

系统会自动下载并发送下载结果通知：

```
下载成功
```

### 批量下载

支持同时下载多首歌曲，用逗号分隔：

```
0,1,2
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