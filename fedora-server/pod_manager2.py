#!/usr/bin/env python3

import subprocess
import os
import sys
import time
import yaml
import re
import argparse
import shutil
from typing import List, Dict, Optional, Tuple, Set
from pathlib import Path

class EnhancedPodManager:
    def __init__(self):
        self.backend_comm_network = "backend_comm"
        self.macvlan_network = "macvlan"
        
        # Convert relative paths to absolute paths
        base_dir = Path(__file__).parent.absolute()
        self.pods = [
            ("pod1-core", str(base_dir / "PODMAN/pods/pod1-core/podman-compose.yml")),
            ("pod2-monitoring", str(base_dir / "PODMAN/pods/pod2-monitoring/podman-compose.yml")),
            ("pod3-logging", str(base_dir / "PODMAN/pods/pod3-logging/podman-compose.yml")),
            ("pod4-security", str(base_dir / "PODMAN/pods/pod4-security/podman-compose.yml")),
            ("pod5-intelligence", str(base_dir / "PODMAN/pods/pod5-intelligence/podman-compose.yml")),
            ("pod6-network", str(base_dir / "PODMAN/pods/pod6-network/podman-compose.yml")),
        ]
        self.selinux_enabled = self._check_selinux_status()
        self.is_rootless = self._check_rootless_mode()
        
    def _check_selinux_status(self) -> bool:
        """Check if SELinux is enabled and enforcing."""
        try:
            rc, stdout, stderr = self.run_command("getenforce", shell=False)
            if rc == 0 and stdout.strip().lower() in ['enforcing', 'permissive']:
                print(f"SELinux detected: {stdout.strip()}")
                return True
            return False
        except:
            return False
    
    def _check_rootless_mode(self) -> bool:
        """Check if running in rootless mode."""
        return os.getuid() != 0
    
    def run_command(self, command: str, shell: bool = True, cwd: Optional[str] = None, 
                   retry_count: int = 0, retry_delay: int = 2) -> Tuple[int, str, str]:
        """Run a shell command with retry capability and return the result."""
        for attempt in range(retry_count + 1):
            try:
                if attempt > 0:
                    print(f"Retrying command (attempt {attempt + 1}/{retry_count + 1}): {command}")
                    time.sleep(retry_delay)
                
                process = subprocess.Popen(
                    command,
                    shell=shell,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=cwd
                )
                stdout, stderr = process.communicate()
                
                if process.returncode == 0 or attempt == retry_count:
                    return process.returncode, stdout, stderr
                    
            except Exception as e:
                if attempt == retry_count:
                    return 1, "", str(e)
        
        return process.returncode, stdout, stderr

    def get_pod_names(self) -> List[str]:
        """Get list of all configured pod names."""
        return [pod[0] for pod in self.pods]

    def get_pod_compose_path(self, pod_name: str) -> Optional[str]:
        """Get compose file path for a specific pod."""
        for name, path in self.pods:
            if name == pod_name:
                return path
        return None

    def validate_compose_file(self, compose_path: str) -> Tuple[bool, List[str]]:
        """Validate compose file for common SELinux and rootless issues."""
        issues = []
        
        if not os.path.exists(compose_path):
            issues.append(f"Compose file not found: {compose_path}")
            return False, issues
        
        # Check if parent directory exists
        compose_dir = os.path.dirname(compose_path)
        if not os.path.exists(compose_dir):
            issues.append(f"Compose file directory does not exist: {compose_dir}")
            return False, issues
            
        try:
            with open(compose_path, 'r') as f:
                compose_data = yaml.safe_load(f)
                
            services = compose_data.get('services', {})
            
            for service_name, service_config in services.items():
                volumes = service_config.get('volumes', [])
                
                for volume in volumes:
                    if isinstance(volume, str):
                        issue = self._validate_volume_mount(volume, service_name, compose_path)
                        if issue:
                            issues.append(issue)
                            
        except Exception as e:
            issues.append(f"Error parsing compose file {compose_path}: {str(e)}")
            
        return len(issues) == 0, issues
    
    def _validate_volume_mount(self, volume: str, service_name: str, compose_path: str) -> Optional[str]:
        """Validate individual volume mount for SELinux and rootless issues."""
        # Check for malformed mount syntax
        if volume.count(':') < 1:
            return None
            
        parts = volume.split(':')
        if len(parts) < 2:
            return None
            
        host_path = parts[0]
        container_path = parts[1]
        options = ':'.join(parts[2:]) if len(parts) > 2 else ""
        
        # Check for system directory mounting with SELinux relabeling
        system_dirs = ['/var/log', '/etc', '/home', '/usr', '/boot', '/sys', '/proc']
        if any(host_path.startswith(sys_dir) for sys_dir in system_dirs):
            if 'z' in options.lower() or 'Z' in options.lower():
                return f"Service {service_name} in {compose_path}: SELinux will block relabeling of system directory {host_path}. Remove :z/:Z or use alternative approach."
        
        # Improved malformed options detection
        if re.search(r'[zZ]:[zZ]', options):
            return f"Service {service_name} in {compose_path}: Invalid volume option format in '{volume}'. Use 'z' or 'Z', not 'z:z'."
        
        # Check for multiple z/Z options
        z_count = options.lower().count('z')
        if z_count > 1:
            return f"Service {service_name} in {compose_path}: Multiple SELinux options detected in '{volume}'. Use only one 'z' or 'Z'."
            
        # Check for non-existent host paths (only absolute paths)
        if host_path.startswith('/') and not os.path.exists(host_path):
            return f"Service {service_name} in {compose_path}: Host path does not exist: {host_path}"
            
        return None
    
    def fix_compose_file_issues(self, compose_path: str) -> bool:
        """Attempt to automatically fix common compose file issues."""
        try:
            with open(compose_path, 'r') as f:
                content = f.read()
                
            original_content = content
            
            # Fix malformed SELinux options (z:z -> z, Z:Z -> Z)
            content = re.sub(r':z:z\b', ':z', content)
            content = re.sub(r':Z:Z\b', ':Z', content)
            
            # Remove SELinux relabeling from system directories
            system_dirs = ['/var/log', '/etc', '/home', '/usr', '/boot']
            for sys_dir in system_dirs:
                # Remove :z and :Z from system directory mounts
                pattern = fr'({re.escape(sys_dir)}[^:\s]*:[^:\s]*):z\b'
                content = re.sub(pattern, r'\1', content)
                pattern = fr'({re.escape(sys_dir)}[^:\s]*:[^:\s]*):Z\b'
                content = re.sub(pattern, r'\1', content)
            
            # Add userns_mode: keep-id to services if rootless and not present
            if self.is_rootless:
                content = self._add_userns_mode_to_compose(content)
            
            if content != original_content:
                # Create backup
                backup_path = f"{compose_path}.backup.{int(time.time())}"
                with open(backup_path, 'w') as f:
                    f.write(original_content)
                print(f"Created backup: {backup_path}")
                
                # Write fixed content
                with open(compose_path, 'w') as f:
                    f.write(content)
                print(f"Fixed compose file: {compose_path}")
                return True
                
        except Exception as e:
            print(f"Error fixing compose file {compose_path}: {str(e)}")
            return False
            
        return True

    def _add_userns_mode_to_compose(self, content: str) -> str:
        """Add userns_mode: keep-id to services that don't have it."""
        try:
            compose_data = yaml.safe_load(content)
            services = compose_data.get('services', {})
            
            modified = False
            for service_name, service_config in services.items():
                if 'userns_mode' not in service_config:
                    service_config['userns_mode'] = 'keep-id'
                    modified = True
                    print(f"Added userns_mode: keep-id to service {service_name}")
            
            if modified:
                return yaml.dump(compose_data, default_flow_style=False, sort_keys=False)
            
        except Exception as e:
            print(f"Error adding userns_mode to compose content: {str(e)}")
        
        return content

    def ensure_network_exists(self, network_name: str) -> bool:
        """Ensure a network exists, create it if it doesn't."""
        print(f"Ensuring {network_name} network exists...")
        
        # Check if network exists
        rc, stdout, stderr = self.run_command(f"podman network inspect {network_name}", retry_count=1)
        
        if rc == 0:
            print(f"Network {network_name} already exists")
            return True
            
        print(f"Creating {network_name} network...")
        
        # Skip macvlan networks in rootless mode - they don't work
        if network_name == self.macvlan_network and self.is_rootless:
            print(f"Skipping macvlan network {network_name} in rootless mode - not supported")
            return True
        
        # Create network with appropriate options
        if network_name == self.macvlan_network and not self.is_rootless:
            # Special handling for macvlan networks (root mode only)
            rc, stdout, stderr = self.run_command(
                f"podman network create --driver macvlan {network_name}",
                retry_count=2
            )
        else:
            rc, stdout, stderr = self.run_command(
                f"podman network create {network_name}",
                retry_count=2
            )
            
        if rc != 0:
            print(f"Error creating network {network_name}: {stderr}")
            # Try alternative network creation
            if "already exists" in stderr.lower():
                print(f"Network {network_name} was created by another process")
                return True
            return False
            
        print(f"Successfully created network {network_name}")
        return True

    def stop_and_remove_pod(self, pod_name: str) -> bool:
        """Stop and remove a pod if it exists with improved error handling."""
        compose_path = self.get_pod_compose_path(pod_name)
        if not compose_path:
            print(f"Pod {pod_name} not found in configuration")
            return False
            
        compose_dir = os.path.dirname(compose_path)
        
        print(f"Stopping and removing pod {pod_name}...")
        
        # Use podman-compose down to properly stop and remove services
        rc, stdout, stderr = self.run_command(
            "podman-compose -f podman-compose.yml down",
            cwd=compose_dir,
            retry_count=1
        )
        
        if rc != 0:
            print(f"Warning: Error during compose down for {pod_name}: {stderr}")
            # Continue anyway - might be already down
        
        # Also try to remove the actual pod if it exists
        actual_pod_name = f"pod_{pod_name}"
        rc, stdout, stderr = self.run_command(f"podman pod exists {actual_pod_name}")
        if rc == 0:
            # Pod exists, try to remove it
            rc, stdout, stderr = self.run_command(f"podman pod rm -f {actual_pod_name}", retry_count=2)
            if rc != 0 and "no such pod" not in stderr.lower():
                print(f"Warning: Could not remove pod {actual_pod_name}: {stderr}")
        
        print(f"Stopped and removed services for {pod_name}")
        return True

    def create_pod(self, pod_name: str) -> bool:
        """Create a new pod with improved error handling."""
        actual_pod_name = f"pod_{pod_name}"
        
        print(f"Creating pod {actual_pod_name}...")
        
        # Check if pod already exists
        rc, stdout, stderr = self.run_command(f"podman pod exists {actual_pod_name}")
        if rc == 0:
            print(f"Pod {actual_pod_name} already exists")
            return True
        
        # Create pod with appropriate options for rootless
        cmd_parts = ["podman", "pod", "create", "--name", actual_pod_name]
        
        # Add network
        cmd_parts.extend(["--network", self.backend_comm_network])
        
        # Note: We do NOT add --userns keep-id here as it conflicts with podman-compose
        
        cmd = " ".join(cmd_parts)
        rc, stdout, stderr = self.run_command(cmd, retry_count=1)
        
        if rc != 0:
            if any(phrase in stderr.lower() for phrase in ['already exists', 'name is in use']):
                print(f"Pod {actual_pod_name} was created by another process")
                return True
            print(f"Error creating pod {actual_pod_name}: {stderr}")
            return False
            
        print(f"Successfully created pod {actual_pod_name}")
        return True

    def bring_up_pod_services(self, pod_name: str) -> bool:
        """Bring up pod services with enhanced error handling."""
        compose_path = self.get_pod_compose_path(pod_name)
        if not compose_path:
            print(f"Pod {pod_name} not found in configuration")
            return False
            
        pod_dir = os.path.dirname(compose_path)
        
        # Validate compose file first
        is_valid, issues = self.validate_compose_file(compose_path)
        if not is_valid:
            print(f"Compose file validation failed for {pod_name}:")
            for issue in issues:
                print(f"  - {issue}")
            
            # Attempt to fix issues automatically
            print(f"Attempting to fix issues in {compose_path}...")
            if self.fix_compose_file_issues(compose_path):
                print("Issues fixed, re-validating...")
                is_valid, remaining_issues = self.validate_compose_file(compose_path)
                if remaining_issues:
                    print("Remaining issues:")
                    for issue in remaining_issues:
                        print(f"  - {issue}")
        
        print(f"Bringing up services for {pod_name} using {compose_path}...")
        
        # FIXED: Remove --userns=keep-id from podman-compose command
        # This was causing the "--userns and --pod cannot be set together" error
        cmd_parts = ["podman-compose", "-f", "podman-compose.yml", "up", "-d"]
        
        # Set environment variables for better compatibility
        env = os.environ.copy()
        if self.selinux_enabled:
            env['PODMAN_SELINUX'] = '1'
        
        cmd = " ".join(cmd_parts)
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=pod_dir,
            env=env
        )
        stdout, stderr = process.communicate()
        rc = process.returncode
        
        if rc != 0:
            print(f"Error bringing up services for {pod_name}: {stderr}")
            
            # Provide specific guidance based on error patterns
            if "selinux relabeling" in stderr.lower():
                print("SELinux relabeling error detected. This usually means:")
                print("  - Trying to relabel system directories like /var/log, /etc")
                print("  - Remove :z or :Z from system directory mounts")
                print("  - Use read-only mounts without relabeling for system dirs")
                
            elif "permission denied" in stderr.lower():
                print("Permission denied error detected. This could be:")
                print("  - SELinux blocking access (check audit logs)")
                print("  - User namespace mapping issues in rootless mode")
                print("  - File ownership problems")
                
            elif "could not parse mount" in stderr.lower():
                print("Mount parsing error detected. Check for:")
                print("  - Malformed volume syntax (e.g., extra colons)")
                print("  - Invalid mount options")
                
            return False
        
        print(f"Successfully brought up services for {pod_name}")
        if stdout:
            print(stdout)
        return True

    def check_system_prerequisites(self) -> bool:
        """Check system prerequisites and configuration."""
        print("Checking system prerequisites...")
        
        issues = []
        
        # Check podman installation
        rc, stdout, stderr = self.run_command("podman --version")
        if rc != 0:
            issues.append("Podman is not installed or not in PATH")
        else:
            print(f"Podman version: {stdout.strip()}")
        
        # Check podman-compose installation
        rc, stdout, stderr = self.run_command("podman-compose --version")
        if rc != 0:
            issues.append("podman-compose is not installed or not in PATH")
        else:
            print(f"podman-compose version: {stdout.strip()}")
        
        # Check user namespace configuration for rootless
        if self.is_rootless:
            subuid_path = f"/etc/subuid"
            subgid_path = f"/etc/subgid"
            username = os.getenv('USER')
            
            if not os.path.exists(subuid_path):
                issues.append(f"{subuid_path} not found - needed for rootless containers")
            else:
                with open(subuid_path, 'r') as f:
                    if username not in f.read():
                        issues.append(f"User {username} not configured in {subuid_path}")
        
        # Check SELinux container policy
        if self.selinux_enabled:
            rc, stdout, stderr = self.run_command("rpm -q container-selinux")
            if rc != 0:
                issues.append("container-selinux package not installed - needed for SELinux container support")
        
        # Print issues
        if issues:
            print("System prerequisite issues found:")
            for issue in issues:
                print(f"  - {issue}")
            return False
        
        print("System prerequisites check passed")
        return True

    def get_pod_status(self, pod_name: str) -> Dict[str, str]:
        """Get status information for a specific pod."""
        compose_path = self.get_pod_compose_path(pod_name)
        if not compose_path:
            return {"status": "unknown", "error": "Pod not found in configuration"}
        
        compose_dir = os.path.dirname(compose_path)
        
        # Check if compose file exists
        if not os.path.exists(compose_path):
            return {"status": "error", "error": f"Compose file not found: {compose_path}"}
        
        # Use podman-compose ps to get status
        rc, stdout, stderr = self.run_command(
            "podman-compose -f podman-compose.yml ps",
            cwd=compose_dir
        )
        
        if rc != 0:
            return {"status": "error", "error": f"Failed to get status: {stderr}"}
        
        # Parse output to determine overall status
        if "Up" in stdout:
            return {"status": "running", "details": stdout}
        elif "Exit" in stdout:
            return {"status": "stopped", "details": stdout}
        else:
            return {"status": "unknown", "details": stdout}

    def validate_all_compose_files(self) -> bool:
        """Validate all compose files without making changes."""
        print("Validating all compose files...")
        
        overall_valid = True
        
        for pod_name, compose_path in self.pods:
            print(f"\nValidating {pod_name}: {compose_path}")
            is_valid, issues = self.validate_compose_file(compose_path)
            
            if is_valid:
                print(f"  ✓ {pod_name}: Valid")
            else:
                print(f"  ✗ {pod_name}: Issues found:")
                for issue in issues:
                    print(f"    - {issue}")
                overall_valid = False
        
        return overall_valid

    # Command handlers
    def handle_up(self, pod_names: List[str]) -> bool:
        """Handle 'up' command for specified pods."""
        if not self.check_system_prerequisites():
            print("System prerequisites check failed")
            return False
        
        # Ensure networks exist
        print("\n=== Network Setup ===")
        for network in [self.backend_comm_network, self.macvlan_network]:
            if not self.ensure_network_exists(network):
                print(f"Failed to ensure {network} network exists")
                return False
        
        overall_success = True
        
        for pod_name in pod_names:
            print(f"\n=== Bringing up {pod_name} ===")
            
            # Stop and remove existing pod
            if not self.stop_and_remove_pod(pod_name):
                print(f"Failed to stop and remove pod {pod_name}")
                overall_success = False
                continue
            
            # Create new pod
            if not self.create_pod(pod_name):
                print(f"Failed to create pod {pod_name}")
                overall_success = False
                continue
            
            # Bring up services
            if not self.bring_up_pod_services(pod_name):
                print(f"Failed to bring up services for pod {pod_name}")
                overall_success = False
                continue
            
            print(f"✓ Successfully brought up {pod_name}")
            time.sleep(2)  # Brief pause between pods
        
        return overall_success

    def handle_down(self, pod_names: List[str]) -> bool:
        """Handle 'down' command for specified pods."""
        overall_success = True
        
        for pod_name in pod_names:
            print(f"\n=== Bringing down {pod_name} ===")
            
            if not self.stop_and_remove_pod(pod_name):
                print(f"Failed to stop and remove pod {pod_name}")
                overall_success = False
                continue
            
            print(f"✓ Successfully brought down {pod_name}")
        
        return overall_success

    def handle_restart(self, pod_names: List[str]) -> bool:
        """Handle 'restart' command for specified pods."""
        return self.handle_up(pod_names)

    def handle_status(self) -> bool:
        """Handle 'status' command - show status of all pods."""
        print("Pod Status Report:")
        print("=" * 50)
        
        for pod_name, _ in self.pods:
            status_info = self.get_pod_status(pod_name)
            status = status_info.get("status", "unknown")
            
            status_symbol = {
                "running": "🟢",
                "stopped": "🔴", 
                "error": "❌",
                "unknown": "🟡"
            }.get(status, "❓")
            
            print(f"{status_symbol} {pod_name}: {status}")
            
            if "error" in status_info:
                print(f"    Error: {status_info['error']}")
        
        return True

def main():
    parser = argparse.ArgumentParser(
        description="Enhanced Podman Pod Manager with selective operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s up all                           # Bring up all pods
  %(prog)s up pod2-monitoring pod3-logging  # Bring up specific pods
  %(prog)s down pod2-monitoring             # Stop specific pod
  %(prog)s restart pod3-logging             # Restart specific pod
  %(prog)s status                           # Show status of all pods
  %(prog)s validate                         # Validate all compose files
        """
    )
    
    parser.add_argument(
        'action',
        choices=['up', 'down', 'restart', 'status', 'validate'],
        help='Action to perform'
    )
    
    parser.add_argument(
        'pods',
        nargs='*',
        help='Pod names to operate on (use "all" for all pods, or specific pod names)'
    )
    
    args = parser.parse_args()
    
    pod_manager = EnhancedPodManager()
    
    # Handle pod selection
    if args.action in ['up', 'down', 'restart']:
        if not args.pods:
            print(f"Error: {args.action} command requires pod names or 'all'")
            sys.exit(1)
        
        if 'all' in args.pods:
            selected_pods = pod_manager.get_pod_names()
        else:
            # Validate pod names
            valid_pods = pod_manager.get_pod_names()
            selected_pods = []
            for pod in args.pods:
                if pod in valid_pods:
                    selected_pods.append(pod)
                else:
                    print(f"Error: Unknown pod '{pod}'. Valid pods: {', '.join(valid_pods)}")
                    sys.exit(1)
    
    # Execute the requested action
    success = False
    
    if args.action == 'up':
        success = pod_manager.handle_up(selected_pods)
    elif args.action == 'down':
        success = pod_manager.handle_down(selected_pods)
    elif args.action == 'restart':
        success = pod_manager.handle_restart(selected_pods)
    elif args.action == 'status':
        success = pod_manager.handle_status()
    elif args.action == 'validate':
        success = pod_manager.validate_all_compose_files()
    
    if success:
        print(f"\n🎉 Successfully completed {args.action} operation")
        sys.exit(0)
    else:
        print(f"\n❌ Failed to complete {args.action} operation")
        sys.exit(1)

if __name__ == "__main__":
    main()
