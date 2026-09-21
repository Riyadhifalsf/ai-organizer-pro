import paramiko
key_path=r"C:\Users\Babeh\.ssh\opencode_pve"
s=paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect("192.168.100.10", username="root", key_filename=key_path, timeout=8, allow_agent=False, look_for_keys=False)
def run(cmd, timeout=60):
    stdin, stdout, stderr = s.exec_command(cmd, timeout=timeout)
    rc=stdout.channel.recv_exit_status()
    out=stdout.read().decode("utf-8", errors="replace")
    err=stderr.read().decode("utf-8", errors="replace")
    print(f"$ {cmd} [rc={rc}]\n{out}\n{err}\n")
# permissions agar kebaca unprivileged CT (100000) + samba tetap bisa
run("chown -R 100000:100000 /mnt/media/foto /mnt/media/video; chmod -R 775 /mnt/media/foto /mnt/media/video; setfacl -R -m u:mediauser:rwx /mnt/media/foto /mnt/media/video 2>&1; ls -ld /mnt/media/foto /mnt/media/video")
# bind mount hanya foto & video, bukan semuanya
run("pct stop 102 --timeout 30; sleep 3; pct set 102 -mp0 /mnt/media/foto,mp=/mnt/foto,backup=0 -mp1 /mnt/media/video,mp=/mnt/video,backup=0; cat /etc/pve/lxc/102.conf")
run("pct start 102; sleep 5; pct status 102; pct exec 102 -- sh -c 'ls -la /mnt/; ls -la /mnt/foto; ls -la /mnt/video; df -h /mnt/foto /mnt/video'")
s.close()
