from flask import Flask, Response
import requests
import os
import sys
import json
import base64
import time
import platform
import subprocess
import threading
import re
from pathlib import Path
import random
import string

app = Flask(__name__)

# 环境变量
UPLOAD_URL = os.environ.get('UPLOAD_URL', '')
PROJECT_URL = os.environ.get('PROJECT_URL', '')
AUTO_ACCESS = os.environ.get('AUTO_ACCESS', 'false').lower() in ('1','true','yes')
FILE_PATH = os.environ.get('FILE_PATH', './tmp')
SUB_PATH = os.environ.get('SUB_PATH', 'sub')
PORT = int(os.environ.get('SERVER_PORT') or os.environ.get('PORT') or 3000)
UUID = os.environ.get('UUID', '9afd1229-b893-40c1-84dd-51e7ce204913')
NEZHA_SERVER = os.environ.get('NEZHA_SERVER', '')
NEZHA_PORT = os.environ.get('NEZHA_PORT', '')
NEZHA_KEY = os.environ.get('NEZHA_KEY', '')
ARGO_DOMAIN = os.environ.get('ARGO_DOMAIN', '')
ARGO_AUTH = os.environ.get('ARGO_AUTH', '')
ARGO_PORT = int(os.environ.get('ARGO_PORT', 8001))
CFIP = os.environ.get('CFIP', 'cdns.doon.eu.org')
CFPORT = os.environ.get('CFPORT', '443')
NAME = os.environ.get('NAME', '')

# 确保目录存在
Path(FILE_PATH).mkdir(parents=True, exist_ok=True)
print(f"Using file path: {FILE_PATH}")

# 生成随机6位名字
def generate_random_name():
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(6))

npmName = generate_random_name()
webName = generate_random_name()
botName = generate_random_name()
phpName = generate_random_name()
npmPath = str(Path(FILE_PATH) / npmName)
phpPath = str(Path(FILE_PATH) / phpName)
webPath = str(Path(FILE_PATH) / webName)
botPath = str(Path(FILE_PATH) / botName)
subPath = str(Path(FILE_PATH) / 'sub.txt')
listPath = str(Path(FILE_PATH) / 'list.txt')
bootLogPath = str(Path(FILE_PATH) / 'boot.log')
configPath = str(Path(FILE_PATH) / 'config.json')

# 全局变量用于 /SUB 路由
_encoded_sub = None

# 删除已有节点（向 UPLOAD_URL 发送历史节点）
def delete_nodes():
    if not UPLOAD_URL:
        return
    if not Path(subPath).exists():
        return
    try:
        fileContent = Path(subPath).read_text(encoding='utf-8')
    except Exception:
        return
    try:
        decoded = base64.b64decode(fileContent).decode('utf-8')
    except Exception:
        return
    nodes = [l for l in decoded.splitlines() if re.search(r"(vless|vmess|trojan|hysteria2|tuic):\\/\\/", l)]
    if not nodes:
        return
    try:
        requests.post(f"{UPLOAD_URL}/api/delete-nodes", json={'nodes': nodes}, timeout=6)
    except Exception:
        pass

# 清理历史文件
def cleanup_old_files():
    try:
        for p in Path(FILE_PATH).iterdir():
            try:
                if p.is_file():
                    p.unlink()
            except Exception:
                pass
    except Exception:
        pass

@app.route('/')
def index():
    return 'Hello world!'

# 生成 xr-ay 配置文件
def generate_config():
    config = {
        'log': {'access': '/dev/null', 'error': '/dev/null', 'loglevel': 'none'},
        'inbounds': [
            {'port': ARGO_PORT, 'protocol': 'vless', 'settings': {'clients': [{'id': UUID, 'flow': 'xtls-rprx-vision'}], 'decryption': 'none', 'fallbacks': [{'dest': 3001}, {'path': '/vless-argo', 'dest': 3002}, {'path': '/vmess-argo', 'dest': 3003}, {'path': '/trojan-argo', 'dest': 3004}]}, 'streamSettings': {'network': 'tcp'}},
            {'port': 3001, 'listen': '127.0.0.1', 'protocol': 'vless', 'settings': {'clients': [{'id': UUID}], 'decryption': 'none'}, 'streamSettings': {'network': 'tcp', 'security': 'none'}},
            {'port': 3002, 'listen': '127.0.0.1', 'protocol': 'vless', 'settings': {'clients': [{'id': UUID, 'level': 0}], 'decryption': 'none'}, 'streamSettings': {'network': 'ws', 'security': 'none', 'wsSettings': {'path': '/vless-argo'}}, 'sniffing': {'enabled': True, 'destOverride': ['http','tls','quic'], 'metadataOnly': False}},
            {'port': 3003, 'listen': '127.0.0.1', 'protocol': 'vmess', 'settings': {'clients': [{'id': UUID, 'alterId': 0}]}, 'streamSettings': {'network': 'ws', 'wsSettings': {'path': '/vmess-argo'}}, 'sniffing': {'enabled': True, 'destOverride': ['http','tls','quic'], 'metadataOnly': False}},
            {'port': 3004, 'listen': '127.0.0.1', 'protocol': 'trojan', 'settings': {'clients': [{'password': UUID}]}, 'streamSettings': {'network': 'ws', 'security': 'none', 'wsSettings': {'path': '/trojan-argo'}}, 'sniffing': {'enabled': True, 'destOverride': ['http','tls','quic'], 'metadataOnly': False}},
        ],
        'dns': {'servers': ['https+local://8.8.8.8/dns-query']},
        'outbounds': [{'protocol': 'freedom', 'tag': 'direct'}, {'protocol': 'blackhole', 'tag': 'block'}]
    }
    Path(configPath).write_text(json.dumps(config, indent=2), encoding='utf-8')

# 系统架构检测
def get_system_architecture():
    arch = platform.machine().lower()
    if arch.startswith('arm') or 'aarch64' in arch:
        return 'arm'
    return 'amd'

# 下载单个文件
def download_file(file_name, file_url):
    try:
        Path(FILE_PATH).mkdir(parents=True, exist_ok=True)
        resp = requests.get(file_url, stream=True, timeout=20)
        resp.raise_for_status()
        with open(file_name, 'wb') as f:
            for chunk in resp.iter_content(1024*32):
                if chunk:
                    f.write(chunk)
        print(f"Download {Path(file_name).name} successfully")
        return file_name
    except Exception as e:
        print(f"Download {Path(file_name).name} failed: {e}")
        return None

# 根据架构返回需要下载的文件
def get_files_for_architecture(architecture):
    base_files = []
    if architecture == 'arm':
        base_files = [
            {'fileName': webPath, 'fileUrl': 'https://arm64.ssss.nyc.mn/web'},
            {'fileName': botPath, 'fileUrl': 'https://arm64.ssss.nyc.mn/bot'}
        ]
    else:
        base_files = [
            {'fileName': webPath, 'fileUrl': 'https://amd64.ssss.nyc.mn/web'},
            {'fileName': botPath, 'fileUrl': 'https://amd64.ssss.nyc.mn/bot'}
        ]

    if NEZHA_SERVER and NEZHA_KEY:
        if NEZHA_PORT:
            npmUrl = 'https://arm64.ssss.nyc.mn/agent' if architecture == 'arm' else 'https://amd64.ssss.nyc.mn/agent'
            base_files.insert(0, {'fileName': npmPath, 'fileUrl': npmUrl})
        else:
            phpUrl = 'https://arm64.ssss.nyc.mn/v1' if architecture == 'arm' else 'https://amd64.ssss.nyc.mn/v1'
            base_files.insert(0, {'fileName': phpPath, 'fileUrl': phpUrl})
    return base_files

# 下载并运行文件
def download_files_and_run():
    architecture = get_system_architecture()
    files = get_files_for_architecture(architecture)
    if not files:
        print("Can't find a file for the current architecture")
        return
    downloaded = []
    for info in files:
        res = download_file(info['fileName'], info['fileUrl'])
        if res:
            downloaded.append(res)
    # 授权
    files_to_authorize = [npmPath, webPath, botPath] if NEZHA_PORT else [phpPath, webPath, botPath]
    for f in files_to_authorize:
        try:
            if Path(f).exists():
                os.chmod(f, 0o775)
        except Exception:
            pass
    # 运行 ne-zha
    if NEZHA_SERVER and NEZHA_KEY:
        if not NEZHA_PORT:
            # v1
            cfg = f"client_secret: {NEZHA_KEY}\n...\nuuid: {UUID}"
            try:
                Path(Path(FILE_PATH)/'config.yaml').write_text(cfg, encoding='utf-8')
                cmd = f"{phpPath} -c \"{Path(FILE_PATH)/'config.yaml'}\""
                subprocess.Popen(cmd, shell=True)
                print(f"{phpName} is running")
                time.sleep(1)
            except Exception as e:
                print(f"php running error: {e}")
        else:
            try:
                NEZHA_TLS = '--tls' if NEZHA_PORT in ('443','8443','2096','2087','2083','2053') else ''
                cmd = f"{npmPath} -s {NEZHA_SERVER}:{NEZHA_PORT} -p {NEZHA_KEY} {NEZHA_TLS} --disable-auto-update --report-delay 4 --skip-conn --skip-procs"
                subprocess.Popen(cmd, shell=True)
                print(f"{npmName} is running")
                time.sleep(1)
            except Exception as e:
                print(f"npm running error: {e}")
    else:
        print('NEZHA variable is empty,skip running')
    # 运行 xr-ay
    try:
        cmd = f"{webPath} -c {configPath}"
        subprocess.Popen(cmd, shell=True)
        print(f"{webName} is running")
        time.sleep(1)
    except Exception as e:
        print(f"web running error: {e}")
    # 运行 cloudflared(bots)
    if Path(botPath).exists():
        args = ''
        if ARGO_AUTH and re.match(r'^[A-Z0-9a-z=]{120,250}$', ARGO_AUTH):
            args = f"tunnel --edge-ip-version auto --no-autoupdate --protocol http2 run --token {ARGO_AUTH}"
        elif ARGO_AUTH and 'TunnelSecret' in ARGO_AUTH:
            args = f"tunnel --edge-ip-version auto --config {Path(FILE_PATH)/'tunnel.yml'} run"
        else:
            args = f"tunnel --edge-ip-version auto --no-autoupdate --protocol http2 --logfile {bootLogPath} --loglevel info --url http://localhost:{ARGO_PORT}"
        try:
            subprocess.Popen(f"{botPath} {args}", shell=True)
            print(f"{botName} is running")
            time.sleep(2)
        except Exception as e:
            print(f"Error executing command: {e}")
    time.sleep(5)

# 解析 boot.log 获取临时隧道域名
async def extract_domains():
    global _encoded_sub
    if ARGO_AUTH and ARGO_DOMAIN:
        argoDomain = ARGO_DOMAIN
        print('ARGO_DOMAIN:', argoDomain)
        await generate_links(argoDomain)
        return
    try:
        text = Path(bootLogPath).read_text(encoding='utf-8')
        domains = re.findall(r"https?:\\/\\/([^ ]*trycloudflare\\.com)\\/?", text)
        if domains:
            argoDomain = domains[0]
            print('ArgoDomain:', argoDomain)
            await generate_links(argoDomain)
        else:
            print('ArgoDomain not found, re-running bot to obtain ArgoDomain')
            try:
                Path(bootLogPath).unlink()
            except Exception:
                pass
            # 尝试结束 bot 进程（平台相关）
            try:
                if sys.platform.startswith('win'):
                    subprocess.call(f"taskkill /f /im {botName}.exe > nul 2>&1", shell=True)
                else:
                    subprocess.call(f"pkill -f \"{botName}\" > /dev/null 2>&1", shell=True)
            except Exception:
                pass
            time.sleep(3)
            args = f"tunnel --edge-ip-version auto --no-autoupdate --protocol http2 --logfile {bootLogPath} --loglevel info --url http://localhost:{ARGO_PORT}"
            try:
                subprocess.Popen(f"{botPath} {args}", shell=True)
                print(f"{botName} is running")
                time.sleep(3)
                await extract_domains()
            except Exception as e:
                print(f"Error executing command: {e}")
    except Exception as e:
        print('Error reading boot.log:', e)

# 获取 ISP 信息
def get_meta_info():
    try:
        r = requests.get('https://ipapi.co/json/', timeout=3)
        data = r.json()
        if data.get('country_code') and data.get('org'):
            return f"{data.get('country_code')}_{data.get('org')}"
    except Exception:
        try:
            r = requests.get('http://ip-api.com/json/', timeout=3)
            data = r.json()
            if data.get('status') == 'success' and data.get('countryCode') and data.get('org'):
                return f"{data.get('countryCode')}_{data.get('org')}"
        except Exception:
            pass
    return 'Unknown'

# 生成 list 和 sub 信息
async def generate_links(argoDomain):
    global _encoded_sub
    ISP = get_meta_info()
    nodeName = f"{NAME}-{ISP}" if NAME else ISP
    time.sleep(2)
    VMESS = {'v':'2','ps':nodeName,'add':CFIP,'port':CFPORT,'id':UUID,'aid':'0','scy':'none','net':'ws','type':'none','host':argoDomain,'path':'/vmess-argo?ed=2560','tls':'tls','sni':argoDomain,'alpn':'','fp':'firefox'}
    vmess_b64 = base64.b64encode(json.dumps(VMESS, separators=(',',':')).encode()).decode()
    subTxt = f"\n vless://{UUID}@{CFIP}:{CFPORT}?encryption=none&security=tls&sni={argoDomain}&fp=firefox&type=ws&host={argoDomain}&path=%2Fvless-argo%3Fed%3D2560#{nodeName}\n\nvmess://{vmess_b64}\n\ntrojan://{UUID}@{CFIP}:{CFPORT}?security=tls&sni={argoDomain}&fp=firefox&type=ws&host={argoDomain}&path=%2Ftrojan-argo%3Fed%3D2560#{nodeName}\n"
    encoded = base64.b64encode(subTxt.encode()).decode()
    print(encoded)
    Path(subPath).write_text(encoded, encoding='utf-8')
    print(f"{FILE_PATH}/sub.txt saved successfully")
    # 写入全局变量，Flask 路由会读取
    _encoded_sub = encoded
    # 注册路由内容（路由已存在，使用全局变量）
    upload_nodes()
    return subTxt

# 上传节点或订阅
def upload_nodes():
    try:
        if UPLOAD_URL and PROJECT_URL:
            subscriptionUrl = f"{PROJECT_URL}/{SUB_PATH}"
            jsonData = {'subscription':[subscriptionUrl]}
            r = requests.post(f"{UPLOAD_URL}/api/add-subscriptions", json=jsonData, timeout=6)
            if r.status_code == 200:
                print('Subscription uploaded successfully')
                return r
            return None
        elif UPLOAD_URL:
            if not Path(listPath).exists():
                return
            content = Path(listPath).read_text(encoding='utf-8')
            nodes = [l for l in content.splitlines() if re.search(r"(vless|vmess|trojan|hysteria2|tuic):\\/\\/", l)]
            if not nodes:
                return
            r = requests.post(f"{UPLOAD_URL}/api/add-nodes", json={'nodes': nodes}, timeout=6)
            if r and r.status_code == 200:
                print('Nodes uploaded successfully')
                return r
            return None
        else:
            return
    except Exception:
        return

# 90秒后删除相关文件
def clean_files():
    def _job():
        files_to_delete = [bootLogPath, configPath, webPath, botPath]
        if NEZHA_PORT:
            files_to_delete.append(npmPath)
        elif NEZHA_SERVER and NEZHA_KEY:
            files_to_delete.append(phpPath)
        try:
            if sys.platform.startswith('win'):
                subprocess.call(f"del /f /q {' '.join(files_to_delete)} > nul 2>&1", shell=True)
            else:
                subprocess.call(f"rm -rf {' '.join(files_to_delete)} >/dev/null 2>&1", shell=True)
        except Exception:
            pass
        try:
            os.system('cls' if sys.platform.startswith('win') else 'clear')
        except Exception:
            pass
        print('App is running')
        print('Thank you for using this script, enjoy!')
    t = threading.Timer(90.0, _job)
    t.daemon = True
    t.start()

# 自动访问项目URL
def add_visit_task():
    if not AUTO_ACCESS or not PROJECT_URL:
        print('Skipping adding automatic access task')
        return
    try:
        r = requests.post('https://oooo.serv00.net/add-url', json={'url': PROJECT_URL}, timeout=6)
        print('automatic access task added successfully')
        return r
    except Exception as e:
        print(f'Add automatic access task faild: {e}')
        return None

# Flask 路由：订阅
@app.route(f'/{SUB_PATH}')
def sub_handler():
    global _encoded_sub
    if _encoded_sub:
        return Response(_encoded_sub, mimetype='text/plain; charset=utf-8')
    return Response('', mimetype='text/plain; charset=utf-8')

# 主运行逻辑
def startserver():
    try:
        # argoType() 的最小实现：如果 ARGO_AUTH 包含 TunnelSecret，则写入 tunnel.json 和 tunnel.yml
        if ARGO_AUTH and ARGO_DOMAIN and 'TunnelSecret' in ARGO_AUTH:
            try:
                Path(Path(FILE_PATH)/'tunnel.json').write_text(ARGO_AUTH, encoding='utf-8')
                tunnel_yml = f"\n  tunnel: {json.loads(ARGO_AUTH).get('TunnelSecret','')}\n  credentials-file: {Path(FILE_PATH)/'tunnel.json'}\n  protocol: http2\n\n  ingress:\n    - hostname: {ARGO_DOMAIN}\n      service: http://localhost:{ARGO_PORT}\n      originRequest:\n        noTLSVerify: true\n    - service: http_status:404\n"
                Path(Path(FILE_PATH)/'tunnel.yml').write_text(tunnel_yml, encoding='utf-8')
            except Exception:
                pass
        delete_nodes()
        cleanup_old_files()
        generate_config()
        download_files_and_run()
        # extract_domains 是异步的，调用并等待
        try:
            import asyncio
            asyncio.run(extract_domains())
        except Exception:
            pass
        add_visit_task()
    except Exception as e:
        print('Error in startserver:', e)

if __name__ == '__main__':
    clean_files()
    # 后台启动主逻辑
    t = threading.Thread(target=startserver, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=PORT)
