loginctl enable-linger $USER      # run once, as root or with sudo
systemctl --user enable --now podman.socket
