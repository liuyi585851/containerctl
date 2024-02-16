import subprocess
import sys
import getopt
import os
import json
import requests
import tarfile
from tqdm import tqdm
import hashlib

# 检查软件包是否安装
def check_package(package_name):
    try:
        result=subprocess.run(['dpkg','-s',package_name], capture_output=True,text=True)
        if result.returncode!=0:
            print(f"运行依赖软件包 {package_name} 未安装，正在尝试安装...")
            install_package(package_name)
        else:
            return True
    except Exception as e:
        print(f"发生未知错误，错误原因: {e}")
        
# 安装软件包
def install_package(package_name):
    try:
        result = subprocess.run(['apt','install',package_name], capture_output=True,text=True)
        if result.returncode!=0:
            print(f"软件包 {package_name} 安装失败，请尝试手动安装或检查网络连接")
        else:
            print(f"软件包 {package_name} 安装成功")
    except Exception as e:
        print(f"发生未知错误，错误原因: {e}")

# 文件解压
def untar(file_path, target_path):
    tar = tarfile.open(file_path)
    members = tar.getmembers()
    progress_bar = tqdm(total=len(members), desc="解压中")
    for member in members:
        tar.extract(member, path=target_path)
        progress_bar.update(1)
    progress_bar.close()
    tar.close()

# 文件下载
def download_file(url, headers,path):
    res = requests.get(url, headers=headers,stream=True)
    chunk_size = 1024 * 4
    content_size = int(res.headers['content-length'])
    data_count = 0
    with open(path, "wb") as file:
        progress = tqdm(total=content_size, unit="B", unit_scale=True, desc="下载中")
        for data in res.iter_content(chunk_size=chunk_size):
                progress.update(len(data))
                file.write(data)
                
# 获取token
def get_token(image):  
    url = f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/{image}:pull"
    res = requests.get(url)
    data = json.loads(res.text)
    return data['access_token']
    
# 获取digest
def get_digest(image,tag,name):
    url = f"https://registry-1.docker.io/v2/library/{image}/manifests/{tag}"
    headers = {
        'Authorization': f"Bearer {get_token(image)}"
    }
    res = requests.get(url,headers=headers)
    data = json.loads(res.text)
    sha256 = hashlib.sha256()
    sha256.update(json.dumps(data).encode('utf-8'))
    with open(f"containers/{name}/blobs/sha256/{sha256.hexdigest()}","w") as f:
        json.dump(data,f)
    with open(f"containers/{name}/index.json","w") as f:
        json.dump(data,f)
    manifests = data['manifests']
    for manifest in manifests:
        digest = manifest['digest']
        data_m = get_manifest(image,digest)
        data_m=json.loads(data_m)
        digest = digest.split(":")[1]
        with open(f"containers/{name}/blobs/sha256/{digest}","w") as f:
            json.dump(data_m,f)
    data = data['manifests'][0]
    return data['digest']

# 获取manifest
def get_manifest(image,digest):
    url = f"https://registry-1.docker.io/v2/library/{image}/manifests/{digest}"
    headers = {
        'Authorization': f"Bearer {get_token(image)}",
        'Accept': 'application/vnd.oci.image.manifest.v1+json'
    }
    res = requests.get(url,headers=headers)
    return res.text

# 拉取镜像
def pull_image(image,tag,name):
    data={
        "imageLayoutVersion":"1.0.0"
    }
    with open(f"containers/{name}/oci-layout","w") as f:
        json.dump(data,f)
    os.makedirs(f"containers/{name}/blobs/sha256",exist_ok=True)
    os.makedirs(f"containers/{name}/bundle/rootfs",exist_ok=True)
    manifest = get_manifest(image,get_digest(image,tag,name))
    manifest = json.loads(manifest)
    layers = manifest['layers']
    count=0
    for layer in layers:
        count+=1
        print(f"正在拉取镜像层{count}...")
        url = f"https://registry-1.docker.io/v2/library/{image}/blobs/{layer['digest']}"
        headers = {   
            'Authorization': f"Bearer {get_token(image)}",
            'Accept': 'application/vnd.oci.image.layer.v1.tar+gzip'
        }
        digest = layer['digest']
        sha256 = digest.split(":")[1]
        download_file(url,headers,f"containers/{name}/blobs/sha256/{sha256}")
        untar(f"containers/{name}/blobs/sha256/{sha256}",f"containers/{name}/bundle/rootfs")

def rollback(name):
    try:
        subprocess.run(['rm','-rf',f'containers/{name}'], capture_output=True,text=True)
    except:
        print("回滚失败，请手动删除残留文件")
        
# 创建容器操作
def operation_create():
    try:
        options,args = getopt.getopt(sys.argv[2:], "n:i:", ["name=", "image="])
    except getopt.GetoptError:
        print("参数错误，请检查后重试")
        sys.exit()
    name=''
    image=''
    tag='latest'
    for option, value in options:
        if option in ['-n', '--name']:
            name = value
        if option in ['-i', '--image']:
            image = value
        if option in ['-t', '--tag']:
            tag = value
    if name=='' or image=='':
        print("参数错误，请检查后重试")
        sys.exit()
    try:
        result=subprocess.run(['mkdir',f'containers/{name}'], capture_output=True,text=True)
        if result.returncode!=0:
            print(f"创建容器 {name} 失败，请检查是否已存在")
            sys.exit()
    except Exception as e:
        print(f"发生未知错误，错误原因: {e}")
        sys.exit()
    try:
        print(f"正在拉取镜像 {image}:{tag} ...")
        try:
            pull_image(image,tag,name)
            print(f"拉取镜像 {image}:{tag} 成功")
        except:
            print(f"拉取镜像 {image}:{tag} 失败，请检查网络连接或镜像是否存在")
            rollback(name)
            sys.exit()
    except Exception as e:
        print(f"发生未知错误，错误原因:{e}")
        rollback(name)
        sys.exit()
    try:
        result=subprocess.run(['runc','spec','-b',f'containers/{name}/bundle'], capture_output=True,text=True)
        if result.returncode!=0:
            print(f"生成runc配置文件失败")
            rollback(name)
            sys.exit()
        else:
            print(f"生成runc配置文件成功")
    except Exception as e:
        print(f"发生未知错误，错误原因:{e}")
        rollback(name)
        sys.exit()
    try:
        with open(f'containers/{name}/bundle/config.json','r') as f:
            config=json.load(f)
        config['process']['terminal']=False
        config['process']['args']=['sleep','1000000']
        with open(f'containers/{name}/bundle/config.json','w') as f:
            json.dump(config,f)
    except:
        print(f"发生未知错误")
        rollback(name)
        sys.exit()
    try:
        result=subprocess.run(['runc','create',f'--bundle=containers/{name}/bundle',f'{name}'])
        if result.returncode!=0:
            print(f"创建容器 {name} 失败")
            rollback(name)
            sys.exit()
        else:
            print(f"创建容器 {name} 成功")
    except Exception as e:
        print(f"发生未知错误，错误原因:{e}")
        rollback(name)
        sys.exit()
    try:
        result=subprocess.run(['runc','start',f'{name}'])
        if result.returncode!=0:
            print(f"容器 {name} 启动失败")
            rollback(name)
            sys.exit()
        else:
            print(f"容器 {name} 启动成功")
            print(subprocess.run(['runc','state',f'{name}'], capture_output=True,text=True).stdout)
    except Exception as e:
        print(f"发生未知错误，错误原因:{e}")
        rollback(name)
        sys.exit()

def operation_start():
    try:
        options,args = getopt.getopt(sys.argv[2:], "n:", ["name="])
    except getopt.GetoptError:
        print("参数错误，请检查后重试")
        sys.exit()
    name=''
    for option, value in options:
        if option in ['-n', '--name']:
            name = value
    if name=='':
        print("参数错误，请检查后重试")
        sys.exit()
    try:
        result=subprocess.run(['runc','state',f'{name}'],capture_output=True,text=True)
        if result.returncode!=0:
            print(f"容器 {name} 不存在")
            sys.exit()
    except Exception as e:
        print(f"发生未知错误，错误原因:{e}")
        sys.exit()
    try:
        result1=subprocess.run(['runc','delete',f'{name}'],capture_output=True,text=True)
        result2=subprocess.run(['runc','create',f'--bundle=containers/{name}/bundle',f'{name}'])
        result3=subprocess.run(['runc','start',f'{name}'],capture_output=True,text=True)
        if result1.returncode!=0 or result2.returncode!=0 or result3.returncode!=0:
            print(f"容器 {name} 启动失败")
            sys.exit()
        else:
            print(f"容器 {name} 启动成功")
            print(subprocess.run(['runc','state',f'{name}'], capture_output=True,text=True).stdout)
    except Exception as e:
        print(f"发生未知错误，错误原因:{e}")
        sys.exit()
        
def operation_stop():
    try:
        options,args = getopt.getopt(sys.argv[2:], "n:", ["name="])
    except getopt.GetoptError:
        print("参数错误，请检查后重试")
        sys.exit()
    name=''
    for option, value in options:
        if option in ['-n', '--name']:
            name = value
    if name=='':
        print("参数错误，请检查后重试")
        sys.exit()
    try:
        result=subprocess.run(['runc','state',f'{name}'],capture_output=True,text=True)
        if result.returncode!=0:
            print(f"容器 {name} 不存在")
            sys.exit()
    except Exception as e:
        print(f"发生未知错误，错误原因:{e}")
        sys.exit()
    try:
        result=subprocess.run(['runc','kill',f'{name}','KILL'],capture_output=True,text=True)
        if result.returncode!=0:
            print(f"容器 {name} 停止失败")
            sys.exit()
        else:
            print(f"容器 {name} 已停止运行")
    except Exception as e:
        print(f"发生未知错误，错误原因:{e}")
        sys.exit()

def operation_list():
    try:
        result=subprocess.run(['runc','list'],capture_output=True,text=True)
        if result.returncode!=0:
            print(f"容器列表获取失败")
            sys.exit()
        else:
            print(result.stdout)
    except Exception as e:
        print(f"发生未知错误，错误原因:{e}")
        sys.exit()
    
def operation_delete():
    try:
        options,args = getopt.getopt(sys.argv[2:], "n:", ["name="])
    except getopt.GetoptError:
        print("参数错误，请检查后重试")
        sys.exit()
    name=''
    for option, value in options:
        if option in ['-n', '--name']:
            name = value
    if name=='':
        print("参数错误，请检查后重试")
        sys.exit()
    try:
        result=subprocess.run(['runc','state',f'{name}'],capture_output=True,text=True)
        if result.returncode!=0:
            print(f"容器 {name} 不存在")
            sys.exit()
    except Exception as e:
        print(f"发生未知错误，错误原因:{e}")
        sys.exit()
    try:
        result=subprocess.run(['runc','delete',f'{name}'],capture_output=True,text=True)
        if result.returncode!=0:
            print(f"容器 {name} 删除失败")
            sys.exit()
        else:
            print(f"容器 {name} 删除成功")
    except Exception as e:
        print(f"发生未知错误，错误原因:{e}")
        sys.exit()
    
# 运行权限检查
if os.geteuid()!=0:
    print("权限不足，请使用root用户运行")
    sys.exit()
# 运行依赖检查
check_package("runc")
cmd = sys.argv
cnt=0
for values in cmd:
    if values in ['create','start','stop','list','delete']:
        operation=values
        cnt+=1
if cnt!=1:
    print("指令有误，请检查后重试")
    sys.exit()
if operation=='create':     # 创建容器
    operation_create()
if operation=='start':      # 启动容器
    operation_start()
if operation=='stop':       # 停止容器
    operation_stop()
if operation=='list':       # 列出容器
    operation_list()
if operation=='delete':     # 删除容器
    operation_delete()