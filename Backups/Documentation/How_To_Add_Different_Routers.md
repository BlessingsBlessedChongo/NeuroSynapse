# Add a Cisco router
python manage.py add_device --name CoreSwitch --ip 192.168.1.1 --type cisco_ios --user admin --pass cisco123

# Add a MikroTik router
python manage.py add_device --name EdgeRouter --ip 192.168.88.1 --type mikrotik_routeros --user admin --pass neuro1234

# Add a Juniper router
python manage.py add_device --name CoreRouter --ip 10.0.0.1 --type juniper_junos --user root --pass juniper123

# Add a Huawei router
python manage.py add_device --name AggSwitch --ip 172.16.0.1 --type huawei_vrp --user admin --pass huawei123

# Add the mock server (for development)
python manage.py add_device --name MockRouter --ip 127.0.0.1 --type generic --port 2222 --user admin --pass anything