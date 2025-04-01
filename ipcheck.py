import psycopg2
import json
import socket
import subprocess
import platform
from psycopg2 import Error as PG_Error
from typing import Dict, Optional
import argparse

def check_network(ip: str, port: int) -> Dict[str, bool]:
    """
    检查网络连通性
    参数:
        ip: 目标IP地址
        port: 目标端口
    返回:
        包含网络状态信息的字典
    """
    result = {
        'ip_reachable': False,
        'port_open': False
    }
    
    # 使用ping命令检查IP是否可达
    try:
        # Windows系统使用-n参数，Linux使用-c参数
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        command = ['ping', param, '1', ip]
        
        # 执行ping命令
        output = subprocess.run(command, 
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             timeout=5)
        
        # 检查返回码
        if output.returncode == 0:
            result['ip_reachable'] = True
    except Exception:
        pass
        
    # 检查端口是否开放
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        if sock.connect_ex((ip, port)) == 0:
            result['port_open'] = True
        sock.close()
    except Exception:
        pass
        
    return result

def check_pg_status(pg_ip: str, pg_port: int, dbname: str, 
                  user: str, password: str) -> Dict[str, Optional[bool]]:
    """
    检查PostgreSQL服务状态
    参数:
        pg_ip: PostgreSQL服务器IP
        pg_port: PostgreSQL服务器端口
        dbname: 数据库名称
        user: 数据库用户名
        password: 数据库密码
    返回:
        包含详细状态信息的字典:
        {
            'network_status': 网络检查结果
            'db_connected': 数据库连接状态
            'error': 错误信息
        }
    """
    result = {
        'network_status': None,
        'db_connected': None,
        'error': None
    }
    
    # 先检查网络连通性
    network_status = check_network(pg_ip, pg_port)
    result['network_status'] = network_status
    
    if not network_status['ip_reachable']:
        result['error'] = f"IP地址 {pg_ip} 不可达"
        return result
        
    if not network_status['port_open']:
        result['error'] = f"端口 {pg_port} 未开放"
        return result
        
    # 如果网络正常，检查数据库连接
    try:
        conn = psycopg2.connect(
            host=pg_ip,
            port=pg_port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=5
        )
        try:
            cursor = conn.cursor()
            # Check if this is a standby server
            cursor.execute("SELECT pg_is_in_recovery()")
            is_standby = cursor.fetchone()[0]
            
            if not is_standby:
                # Only create table and insert timestamp on primary
                try:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS login (
                            login_time TIMESTAMP NOT NULL
                        )
                    """)
                    cursor.execute("INSERT INTO login (login_time) VALUES (NOW()) RETURNING login_time")
                    inserted_time = cursor.fetchone()[0]
                    conn.commit()
                    result['db_connected'] = True
                    result['inserted_time'] = inserted_time.strftime("%Y-%m-%d %H:%M:%S")
                    result['is_standby'] = False
                except PG_Error as e:
                    result['db_connected'] = False
                    result['error'] = f"无法插入数据，请手动检查数据库状态: {e}"
            else:
                result['db_connected'] = True
                result['is_standby'] = True
        finally:
            cursor.close()
            conn.close()
    except PG_Error as e:
        result['db_connected'] = False
        result['error'] = f"PostgreSQL连接失败: {e}"
    except Exception as e:
        result['db_connected'] = None
        result['error'] = f"发生未知错误: {e}"
        
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='PostgreSQL实例状态检查工具',
        usage='python pg_pot_ip.py <user> <password> <dbname> <host> <port>'
    )
    parser.add_argument('user', help='PostgreSQL用户名')
    parser.add_argument('password', help='PostgreSQL密码')
    parser.add_argument('dbname', help='PostgreSQL数据库名')
    parser.add_argument('host', help='PostgreSQL服务器地址')
    parser.add_argument('port', type=int, help='PostgreSQL服务器端口')
    
    try:
        args = parser.parse_args()
    except:
        parser.print_help()
        exit(1)
    
    status = check_pg_status(
        args.host,
        args.port,
        args.dbname,
        args.user,
        args.password
    )
    result = {
        "ip": args.host,
        "port": args.port,
        "status": "success" if status['db_connected'] is True else "failed",
        "is_standby": status.get('is_standby', False),
        "network_status": status['network_status'],
        "error": status['error']
    }
    if status['db_connected'] is True and not status.get('is_standby', False):
        result["inserted_time"] = status['inserted_time']
    
    print(f"PostgreSQL IP、端口检查结果:")
    print(f"IP地址: {result['ip']}")
    print(f"端口: {result['port']}")
    print(f"数据库连接状态: {'成功' if result['status'] == 'success' else '失败'}")
    print(f"是否为备库: {'是' if result['is_standby'] else '否'}")
    print(f"网络状态:")
    print(f"  IP可达: {'是' if result['network_status']['ip_reachable'] else '否'}")
    print(f"  端口状态: {'开放' if result['network_status']['port_open'] else '否'}")
    if 'inserted_time' in result:
        print(f"测试数据插入时间: {result['inserted_time']}")
    if result['error']:
        print(f"错误信息: {result['error']}")
