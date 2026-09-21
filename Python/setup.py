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
    return rc
# wipe & single ext4 partition
run("umount /dev/sdb1 2>/dev/null; wipefs -a /dev/sdb; parted /dev/sdb --script mklabel gpt mkpart primary ext4 0% 100%")
run("mkfs.ext4 -L MEDIA -m 1 /dev/sdb1", timeout=300)
run("mkdir -p /mnt/media && UUID=$(blkid -s UUID -o value /dev/sdb1); echo UUID=$UUID; grep -q /mnt/media /etc/fstab || echo \"UUID=$UUID /mnt/media ext4 defaults,nofail 0 2\" >> /etc/fstab; mount -a; df -h /mnt/media")
run("mkdir -p /mnt/media/foto /mnt/media/video; chmod -R 775 /mnt/media; ls -la /mnt/media")
run("pvesm add dir media --path /mnt/media --content images,backup,vztmpl,iso,rootdir --shared 0; pvesm status")
s.close()
