#!/usr/bin/env python3

import subprocess
import os
import sys
import time
from typing import List, Dict, Optional

class PodManager:
    def __init__(self):
        self.backend_comm_network = "backend_comm"
        self.macvlan_network = "macvlan"
        self.pods = [
            ("pod1-core", "PODMAN/pods/pod1-core/podman-compose.yml"),
            ("pod2-monitoring", "PODMAN/pods/pod2-monitoring/podman-compose.yml"),
            ("pod3-logging", "PODMAN/pods/pod3-logging/podman-compose.yml"),
            ("pod4-security", "PODMAN/pods/pod4-security/podman-compose.yml"),
            ("pod5-intelligence", "PODMAN/pods/pod5-intelligence/podman-compose.yml"),
            ("pod6-network", "PODMAN/pods/pod6-network/podman-compose.yml"),
        ]

    def run_command(self, command: str, shell: bool = True, cwd: Optional[str] = None) -> tuple[int, str, str]:
        """Run a shell command and return the result."""
        try:
            process = subprocess.Popen(
                command,
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd
            )
            stdout, stderr = process.communicate()
            return process.returncode, stdout, stderr
        except Exception as e:
            return 1, "", str(e)

    def ensure_network_exists(self, network_name: str) -> bool:
        """Ensure a network exists, create it if it doesn't."""
        print(f"Ensuring {network_name} network exists...")
        rc, stdout, stderr = self.run_command(f"podman network inspect {network_name} 2>/dev/null")
        
        if rc != 0:
            print(f"Creating {network_name} network...")
            rc, stdout, stderr = self.run_command(f"podman network create {network_name}")
            if rc != 0:
                print(f"Error creating network {network_name}: {stderr}")
                return False
        return True

    def stop_and_remove_pod(self, pod_name: str) -> bool:
        actual_pod_name = f"pod_{pod_name}"
        """Stop and remove a pod if it exists."""
        print(f"Stopping pod {actual_pod_name}...")
        # First try to stop the pod
        rc, stdout, stderr = self.run_command(f"podman pod stop {actual_pod_name}")
        
        # Then try to remove it
        print(f"Removing pod {actual_pod_name}...")
        rc, stdout, stderr = self.run_command(f"podman pod rm {actual_pod_name}")
        
        # If normal removal fails, try force removal
        if rc != 0:
            print(f"Attempting force removal of pod {actual_pod_name}...")
            rc, stdout, stderr = self.run_command(f"podman pod rm -f {actual_pod_name}")
            
            if rc != 0 and "no such pod" not in stderr.lower():
                print(f"Error removing pod {actual_pod_name}: {stderr}")
                return False
                
        # Verify pod is actually gone
        rc, stdout, stderr = self.run_command(f"podman pod exists {actual_pod_name}")
        if rc == 0:
            print(f"Pod {actual_pod_name} still exists after removal attempt")
            return False
            
        return True

    def create_pod(self, pod_name: str) -> bool:
        actual_pod_name = f"pod_{pod_name}"
        """Create a new pod with the required networks."""
        print(f"Creating pod for compose: {pod_name} (actual pod name: {actual_pod_name})")
        cmd = f"podman pod create --name {actual_pod_name} --network {self.backend_comm_network}"
        rc, stdout, stderr = self.run_command(cmd)
        if rc != 0:
            if 'already exists' in stderr or 'name \"{actual_pod_name}\" is in use'.format(actual_pod_name=actual_pod_name) in stderr:
                print(f"Pod {actual_pod_name} already exists, continuing...")
                return True
            print(f"Error creating pod {actual_pod_name}: {stderr}")
            return False
        return True

    def bring_up_pod_services(self, pod_name: str, compose_path: str) -> bool:
        pod_dir = os.path.dirname(compose_path)
        print(f"Bringing up services for {pod_name} using {compose_path}...")
        # Using podman-compose with --podman-run-args='--replace' to handle existing containers
        rc, stdout, stderr = self.run_command("podman-compose --podman-run-args='--replace' -f podman-compose.yml up -d", cwd=pod_dir)
        if rc != 0:
            print(f"Error bringing up services for {pod_name}: {stderr}")
            return False
        print(stdout)
        return True

    def cleanup_recreate_and_bringup_pods(self):
        """Clean up existing pods and recreate them."""
        overall_success = True
        # First ensure networks exist
        if not self.ensure_network_exists(self.backend_comm_network):
            print("Failed to ensure backend_comm network exists")
            overall_success = False

        if not self.ensure_network_exists(self.macvlan_network):
            print("Failed to ensure macvlan network exists")
            overall_success = False

        if not overall_success:
            return False

        # Stop and remove existing pods
        for pod, _ in self.pods:
            if not self.stop_and_remove_pod(pod):
                print(f"Failed to clean up pod {pod}")
                overall_success = False

        # Create new pods
        for pod, _ in self.pods:
            if not self.create_pod(pod):
                print(f"Failed to create pod {pod}")
                overall_success = False

        # Bring up services for each pod
        for pod, compose_path in self.pods:
            if not self.bring_up_pod_services(pod, compose_path):
                print(f"Failed to bring up services for pod {pod}")
                overall_success = False

        return overall_success

def main():
    pod_manager = PodManager()
    if pod_manager.cleanup_recreate_and_bringup_pods():
        print("Successfully recreated and started all pods")
    else:
        print("Failed to recreate and start pods")
        sys.exit(1)

if __name__ == "__main__":
    main() 