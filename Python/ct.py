import paramiko
key_path=r"C:\Users\Babeh\.ssh\opencode_pve"
s=paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect("192.168.100.10", username="root", key_filename=key_path, timeout=8, allow_agent=False, look_for_keys=False)
def run(cmd):
    import os
    stdin, stdout, stderr = s.exec_command(cmd, timeout=30)
    rc=stdout.channel.recv_exit_status()
    out=stdout.read().decode("utf-8", errors="replace")
    err=stderr.read().decode("utf-8", errors="replace")
    print(f"$ {cmd} [rc={rc}]\n{out}\n{err}\n")
run("pct list; echo ---; cat /etc/pve/lxc/102.conf; echo ---; pct status 102")
s.close()
