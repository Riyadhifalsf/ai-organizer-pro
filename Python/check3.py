import paramiko
key_path=r"C:\Users\Babeh\.ssh\opencode_pve"
s=paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect("192.168.100.10", username="root", key_filename=key_path, timeout=8, allow_agent=False, look_for_keys=False)
def run(cmd):
    stdin, stdout, stderr = s.exec_command(cmd, environment={"LC_ALL":"C"})
    out=stdout.read().decode("utf-8", errors="replace")
    err=stderr.read().decode("utf-8", errors="replace")
    print(f"=== {cmd} ===\n{out}\n{err}")
run("lsblk -P -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,MODEL")
run("df -h")
run("pvesm status")
run("lvs; echo ---; vgs; echo ---; pvs")
s.close()
