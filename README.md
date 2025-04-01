#使用方法
#示例
#返回结果为json格式
python3 ipcheckjson.py repl postgres postgres 192.168.0.101 5432
#返回结果为普通格式
python3 ipcheck.py repl postgres postgres 192.168.0.101 5432
#说明
本程序功能为检测postgresql数据库VIP地址及端口到数据库底层是否可用
1、检查IP是否可达
2、如果IP可达，检测端口是否可达
3、如果端口可达，使用提供的信息登录数据库
4、如果登录成功，创建一个login测试表，插入一条测试数据
5、上述条件全部成功，结束程序
