import paramiko, socket
users=["admin","user","ubuntu","debian","babeh","nas","truenas","media","server"]
pw="ryhdflsf.123"
for u in users:
    s=paramiko.SSHClient()
    s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        s.connect("192.168.100.10", username=u, password=pw, timeout=4, allow_agent=False, look_for_keys=False)
        print(f"SUCCESS: {u}")
        stdin, stdout, stderr = s.exec_command("whoami; id; lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,MODEL; df -h")
        print(stdout.read().decode()[:3000])
        s.close()
        break
    except Exception as e:
        print(f"{u}: {e}")
