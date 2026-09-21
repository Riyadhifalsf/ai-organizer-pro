import paramiko
key_path=r"C:\Users\Babeh\.ssh\opencode_pve"
s=paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    s.connect("192.168.100.10", username="root", key_filename=key_path, timeout=8, allow_agent=False, look_for_keys=False)
    print("SUCCESS")
    for cmd in ["whoami; hostname", "lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,MODEL", "df -h", "cat /etc/os-release", "pvesm status", "lvs; vgs; pvs"]:
        print(f"=== {cmd} ===")
        stdin, stdout, stderr = s.exec_command(cmd)
        print(stdout.read().decode())
        print(stderr.read().decode())
    s.close()
except Exception as e:
    print(f"FAIL: {e}")
