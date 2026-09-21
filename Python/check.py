import paramiko
s=paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    s.connect("192.168.100.10", username="root", password="ryhdflsf.123", timeout=5)
    for cmd in ["lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,MODEL", "df -h", "cat /etc/os-release", "fdisk -l"]:
        print(f"=== {cmd} ===")
        stdin, stdout, stderr = s.exec_command(cmd)
        print(stdout.read().decode())
        print(stderr.read().decode())
    s.close()
except Exception as e:
    print(f"FAIL: {e}")
