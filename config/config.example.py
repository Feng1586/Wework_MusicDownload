import os

# 企微应用相关配置
# 全部从环境变量读取，这里不写任何默认凭据。
# Docker 部署时变量由 docker-compose 从同目录的 .env 注入；
# 本机直接运行时，可以先设置好同名环境变量再 python main.py，
# 或者把 os.environ.get('STOKEN', "") 的第二参数直接填成你的值。
sToken = os.environ.get('STOKEN', "")
sEncodingAESKey = os.environ.get('S_ENCODING_AES_KEY', "")
sCorpID = os.environ.get('S_CORP_ID', "")
AgentId = int(os.environ.get('AGENT_ID') or 0)
Secret = os.environ.get('SECRET', "")
WeChatProxy = os.environ.get('WECHAT_PROXY', "https://qyapi.weixin.qq.com/")

# 各平台VIP账号Cookies（默认空，留空即用匿名搜索）
QqVipCookies = os.environ.get('QQ_VIP_COOKIES', "")

# 咪咕VIP账号Cookies
MiguVipCookies = os.environ.get('MIGU_VIP_COOKIES', "")

# 网易云VIP账号Cookies
NeteaseVipCookies = os.environ.get('NETEASE_VIP_COOKIES', "")

# 酷我VIP账号Cookies
KuwoVipCookies = os.environ.get('KUWO_VIP_COOKIES', "")

# 千千VIP账号Cookies
QianqianVipCookies = os.environ.get('QIANQIAN_VIP_COOKIES', "")

init_music_clients_cfg = dict()

#显示更多的搜索结果
init_music_clients_cfg['QQMusicClient'] = {'search_size_per_source': 10}
init_music_clients_cfg['MiguMusicClient'] = {'search_size_per_source': 10}
init_music_clients_cfg['NeteaseMusicClient'] = {'search_size_per_source': 10}
init_music_clients_cfg['KuwoMusicClient'] = {'search_size_per_source': 10}
init_music_clients_cfg['QianqianMusicClient'] = {'search_size_per_source': 10}

#设置下载路径
# 注意：从这里开始一律用下标赋值 / update 合并，不要整体重新赋值。
# 原来写成 init_music_clients_cfg['QQMusicClient'] = {'work_dir': 'downloads'}，
# 会把上面刚设好的 search_size_per_source 整个覆盖掉（静默失效）。
init_music_clients_cfg['QQMusicClient']['work_dir'] = 'downloads'

if QqVipCookies:
    init_music_clients_cfg['QQMusicClient'].update({
        'default_search_cookies': QqVipCookies,
        'default_download_cookies': QqVipCookies,
    })

if MiguVipCookies:
    init_music_clients_cfg['MiguMusicClient'].update({
        'default_search_cookies': MiguVipCookies,
        'default_download_cookies': MiguVipCookies,
    })

if NeteaseVipCookies:
    init_music_clients_cfg['NeteaseMusicClient'].update({
        'default_search_cookies': NeteaseVipCookies,
        'default_download_cookies': NeteaseVipCookies,
    })

if KuwoVipCookies:
    init_music_clients_cfg['KuwoMusicClient'].update({
        'default_search_cookies': KuwoVipCookies,
        'default_download_cookies': KuwoVipCookies,
    })

if QianqianVipCookies:
    init_music_clients_cfg['QianqianMusicClient'].update({
        'default_search_cookies': QianqianVipCookies,
        'default_download_cookies': QianqianVipCookies,
    })

#启用哪些下载源
# 支持的源 ['MiguMusicClient', 'NeteaseMusicClient', 'QQMusicClient', 'KuwoMusicClient', 'QianqianMusicClient']
# 这里刻意**不**做成可配置：机器人只与后端约定的 QQMusicClient 交互，
# 下载时也要按 source 取 music_client.music_clients[source]，
# 换源会让后端返回的 source 找不到对应客户端而报错。
src_names = ['QQMusicClient']
