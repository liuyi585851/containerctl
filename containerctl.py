import subprocess
import sys
import getopt
import os
import json
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
        result=subprocess.run(['skopeo','copy',f'docker://docker.io/{image}:{tag}',f'oci:containers/{name}/images'], capture_output=True,text=True)
        if result.returncode!=0:
            print(f"拉取镜像 {image}:{tag} 失败，请检查网络连接或镜像是否存在")
            rollback(name)
            sys.exit()
        else:
            print(f"镜像 {image}:{tag} 拉取成功")
    except Exception as e:
        print(f"发生未知错误，错误原因:{e}")
        rollback(name)
        sys.exit()
    try:
        print(f"正在创建镜像 {image}:{tag} bundle...")
        result=subprocess.run(['oci-image-tool','create','--ref','platform.os=linux',f'containers/{name}/images',f'containers/{name}/images-bundle'], capture_output=True,text=True)
        if result.returncode!=0:
            print(f"创建镜像 {image}:{tag} bundle失败，请检查是否已存在")
            rollback(name)
            sys.exit()
        else:
            print(f"镜像 {image}:{tag} bundle创建成功")
    except Exception as e:
        print(f"发生未知错误，错误原因:{e}")
        rollback(name)
        sys.exit()
    try:
        result=subprocess.run(['rm','-rf',f'containers/{name}/images-bundle/config.json'], capture_output=True,text=True)
        if result.returncode!=0:
            print(f"发生未知错误")
            rollback(name)
            sys.exit()
    except Exception as e:
        print(f"发生未知错误，错误原因:{e}")
        rollback(name)
        sys.exit()
    try:
        result=subprocess.run(['runc','spec','-b',f'containers/{name}/images-bundle'], capture_output=True,text=True)
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
        with open(f'containers/{name}/images-bundle/config.json','r') as f:
            config=json.load(f)
        
        config['process']['terminal']=False
        config['process']['args']=['sleep','1000000']
        with open(f'containers/{name}/images-bundle/config.json','w') as f:
            json.dump(config,f)
    except:
        print(f"发生未知错误")
        rollback(name)
        sys.exit()
    try:
        result=subprocess.run(['runc','create',f'--bundle=containers/{name}/images-bundle',f'{name}'])
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
        result2=subprocess.run(['runc','create',f'--bundle=containers/{name}/images-bundle',f'{name}'])
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
check_package("skopeo")
check_package("oci-image-tool")
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