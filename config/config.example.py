#企微应用相关配置
sToken = "your_token_here"
sEncodingAESKey = "your_encoding_aes_key_here"
sCorpID = "your_corp_id_here"
AgentId = "your_agent_id_here"
Secret = "your_secret_here"
WeChatProxy = "https://qyapi.weixin.qq.com/"

# QQ音乐VIP账号Cookies
QqVipCookies = ""

# 咪咕VIP账号Cookies
MiguVipCookies = ""

# 网易云VIP账号Cookeis
NeteaseVipCookies = ""

# 酷我VIP账号Cookeis
KuwoVipCookies = ""

# 千千VIP账号Cookeis
QianqianVipCookies = ""

init_music_clients_cfg = dict()

#显示更多的搜索结果
init_music_clients_cfg['QQMusicClient'] = {'search_size_per_source': 10}
init_music_clients_cfg['MiguMusicClient'] = {'search_size_per_source': 10}
init_music_clients_cfg['NeteaseMusicClient'] = {'search_size_per_source': 10}
init_music_clients_cfg['KuwoMusicClient'] = {'search_size_per_source': 10}
init_music_clients_cfg['QianqianMusicClient'] = {'search_size_per_source': 10}

#设置下载路径
init_music_clients_cfg['QQMusicClient'] = {'work_dir': 'downloads'}

if QqVipCookies:
    init_music_clients_cfg['QQMusicClient'] = {'default_search_cookies': QqVipCookies, 'default_download_cookies': QqVipCookies}

if MiguVipCookies:
    init_music_clients_cfg['MiguMusicClient'] = {'default_search_cookies': MiguVipCookies, 'default_download_cookies': MiguVipCookies}

if NeteaseVipCookies:
    init_music_clients_cfg['NeteaseMusicClient'] = {'default_search_cookies': NeteaseVipCookies, 'default_download_cookies': NeteaseVipCookies}

if KuwoVipCookies:
    init_music_clients_cfg['KuwoMusicClient'] = {'default_search_cookies': KuwoVipCookies, 'default_download_cookies': KuwoVipCookies}

if QianqianVipCookies:
    init_music_clients_cfg['QianqianMusicClient'] = {'default_search_cookies': QianqianVipCookies, 'default_download_cookies': QianqianVipCookies}

#启用哪些下载源
# 支持的源 ['MiguMusicClient', 'NeteaseMusicClient', 'QQMusicClient', 'KuwoMusicClient', 'QianqianMusicClient']
src_names = ['QQMusicClient']