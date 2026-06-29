use anyhow::{anyhow, Context, Result};
use serde::Deserialize;
use serde_json::json;
use serde_yaml::Value;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use tempfile::NamedTempFile;
use tokio::fs;
use tokio::process::Command;
use users::{get_current_gid, get_current_uid};
use which::which;

#[derive(Debug, Deserialize)]
struct ComposeService {
    ports: Option<Vec<String>>,
}

#[derive(Debug, Deserialize)]
struct ComposeFile {
    services: HashMap<String, ComposeService>,
}

#[derive(Debug)]
pub struct PodConfig {
    pub compose_path: String,
    pub cpu: String,
    pub mem: String,
}

#[derive(Debug)]
pub struct PodManager {
    pub base_path: PathBuf,
    pub pods_config: HashMap<String, PodConfig>,
    pub backend_comm_network: String,
}

impl PodManager {
    pub fn new(base_path: &Path) -> Self {
        let pods_config = [
            ("pod1-core", "pod1-core/podman-compose.yml", "2", "4096"),
            ("pod2-monitoring", "pod2-monitoring/podman-compose.yml", "2", "4096"),
            ("pod3-logging", "pod3-logging/podman-compose.yml", "2", "4096"),
            ("pod4-security", "pod4-security/podman-compose.yml", "2", "4096"),
            ("pod5-intelligence", "pod5-intelligence/podman-compose.yml", "2", "4096"),
            ("pod6-network", "pod6-network/podman-compose.yml", "2", "4096"),
            ("pod7-monitoring", "pod7-monitoring/podman-compose.yml", "2", "4096"),
        ]
        .iter()
        .map(|&(name, compose, cpu, mem)| {
            (
                name.to_string(),
                PodConfig {
                    compose_path: compose.to_string(),
                    cpu: cpu.to_string(),
                    mem: mem.to_string(),
                },
            )
        })
        .collect();

        PodManager {
            base_path: base_path.to_path_buf(),
            pods_config,
            backend_comm_network: "backend_comm".to_string(),
        }
    }

    pub fn get_pod_compose_path(&self, pod_name: &str) -> Option<PathBuf> {
        self.pods_config.get(pod_name).map(|config| {
            self.base_path
                .join("PODMAN")
                .join("pods")
                .join(&config.compose_path)
        })
    }

    pub async fn run_command(&self, command: &str, args: &[&str]) -> Result<()> {
        println!("🔩 Executing: {} {}", command, args.join(" "));
        let status = Command::new(command)
            .args(args)
            .status()
            .await
            .with_context(|| format!("Failed to execute command: {}", command))?;

        if !status.success() {
            return Err(anyhow!(
                "Command failed: {} {}\nExit code: {}",
                command,
                args.join(" "),
                status
            ));
        }

        Ok(())
    }

    pub async fn check_system_prerequisites(&self) -> Result<()> {
        println!("\n=== Checking System Prerequisites ===");
        for cmd in ["podman", "podman-compose"] {
            which(cmd).with_context(|| format!("Critical: '{}' is not installed or not in PATH.", cmd))?;
        }
        println!("✓ Podman and podman-compose are installed.");
        Ok(())
    }

    pub async fn ensure_network_exists(&self, network_name: &str) -> Result<()> {
        let output = Command::new("podman")
            .args(&["network", "exists", network_name])
            .output()
            .await?;

        if output.status.success() {
            println!("✓ Network '{}' already exists.", network_name);
            return Ok(());
        }

        println!("🕸️  Network '{}' not found. Creating...", network_name);

        let network_config = json!({
            "cniVersion": "0.4.0",
            "name": network_name,
            "plugins": [
                {
                    "type": "bridge",
                    "bridge": format!("cni-{}", network_name),
                    "isGateway": true,
                    "ipMasq": true,
                    "ipam": {
                        "type": "host-local",
                        "subnet": "10.89.0.0/24",
                        "routes": [{"dst": "0.0.0.0/0"}]
                    }
                },
                {"type": "portmap", "capabilities": {"portMappings": true}},
                {"type": "firewall"},
                {"type": "tuning"}
            ]
        });

        let temp_file = NamedTempFile::new().context("Failed to create temporary file")?;
        let temp_path = temp_file.path().to_path_buf();
        
        fs::write(&temp_path, network_config.to_string())
            .await
            .context("Failed to write network config to temporary file")?;
        
        println!("📄 Wrote network configuration to {}", temp_path.display());

        self.run_command("podman", &["network", "create", "--file", temp_path.to_str().unwrap(), network_name]).await?;

        println!("✓ Successfully created network '{}'.", network_name);
        
        Ok(())
    }

    pub async fn process_compose_file(&self, pod_name: &str) -> Result<NamedTempFile> {
        let compose_path = self.get_pod_compose_path(pod_name)
            .with_context(|| format!("Compose file path not found for pod '{}'", pod_name))?;

        let original_content = fs::read_to_string(&compose_path)
            .await
            .with_context(|| format!("Failed to read compose file: {}", compose_path.display()))?;

        let uid = get_current_uid().to_string();
        let gid = get_current_gid().to_string();

        let processed_content = original_content
            .replace("$(id -u)", &uid)
            .replace("$(id -g)", &gid);

        let temp_file = NamedTempFile::new().context("Failed to create temporary compose file")?;
        fs::write(temp_file.path(), &processed_content)
            .await
            .with_context(|| "Failed to write processed content to temporary file")?;

        println!("🔧 Processed compose file for '{}' and wrote to {}", pod_name, temp_file.path().display());

        Ok(temp_file)
    }

    pub async fn handle_validate(&self) -> Result<()> {
        println!("\n=== Validating All Compose Files ===");
        let mut all_valid = true;

        for pod_name in self.pods_config.keys() {
            println!("\n🔎 Validating: {}", pod_name);
            match self.process_compose_file(pod_name).await {
                Ok(temp_file) => {
                    match fs::read_to_string(temp_file.path()).await {
                        Ok(content) => {
                             match serde_yaml::from_str::<Value>(&content) {
                                Ok(_) => println!("✓ YAML syntax is valid for {}.", pod_name),
                                Err(e) => {
                                    println!("❌ Error: Invalid YAML for {}: {}", pod_name, e);
                                    all_valid = false;
                                }
                            }
                        }
                        Err(e) => {
                            println!("❌ Error: Could not read temporary file for {}: {}", pod_name, e);
                            all_valid = false;
                        }
                    }
                }
                Err(e) => {
                    println!("❌ Error: Could not process compose file for {}: {}", pod_name, e);
                    all_valid = false;
                }
            }
        }

        if all_valid {
            println!("\n✅ All compose files are valid.");
            Ok(())
        } else {
            Err(anyhow!("Validation failed for one or more compose files."))
        }
    }

    pub async fn handle_up(&self, targets: &[String]) -> Result<()> {
        println!("\n=== Bringing Up Pods and Services ===");

        let mut pod_targets = if targets.contains(&"all".to_string()) || targets.is_empty() {
            self.pods_config.keys().cloned().collect::<Vec<_>>()
        } else {
            targets.to_vec()
        };

        // Ensure pod1-core is always first if it's in the list
        pod_targets.sort_by(|a, b| {
            if a == "pod1-core" {
                std::cmp::Ordering::Less
            } else if b == "pod1-core" {
                std::cmp::Ordering::Greater
            } else {
                a.cmp(b)
            }
        });

        for pod_name in &pod_targets {
            println!("\n--- Handling Pod: {} ---", pod_name);
            self.create_pod_if_not_exists(pod_name).await?;
            self.bring_up_pod_services(pod_name).await?;
        }

        println!("\n✅ All targeted pods and services are up.");
        Ok(())
    }

    async fn bring_up_pod_services(&self, pod_name: &str) -> Result<()> {
        println!("🚀 Bringing up services for pod '{}'...", pod_name);
        let temp_compose_file = self.process_compose_file(pod_name).await?;
        let compose_path = temp_compose_file.path();
        let compose_dir = compose_path.parent().context("Temporary file has no parent directory")?;

        // Special handling for pod1-core's homepage.env file.
        if pod_name == "pod1-core" {
            let env_file_path = compose_dir.join("homepage.env");
            println!("💡 Creating empty env file for homepage: {}", env_file_path.display());
            fs::write(&env_file_path, "").await.context("Failed to create temporary homepage.env")?;
        }

        let compose_path_str = compose_path.to_str()
            .context("Temporary compose file path is not valid UTF-8")?;
        let podman_pod_name = pod_name;

        self.run_command("podman-compose", &[
            "-f", compose_path_str,
            "-p", &podman_pod_name,
            "--podman-run-args=--replace",
            "--podman-run-args=--log-level=debug",
            "up",
        ]).await?;

        println!("✓ Services for pod '{}' are up.", pod_name);
        Ok(())
    }

    async fn create_pod_if_not_exists(&self, pod_name: &str) -> Result<()> {
        let pod_config = self.pods_config.get(pod_name)
            .with_context(|| format!("Configuration for pod '{}' not found", pod_name))?;
        let podman_pod_name = pod_name;

        let output = Command::new("podman")
            .args(&["pod", "exists", &podman_pod_name])
            .output()
            .await?;

        if output.status.success() {
            println!("✓ Pod '{}' already exists.", podman_pod_name);
            return Ok(());
        }

        println!("💡 Pod '{}' not found. Creating...", podman_pod_name);

        let temp_compose_file = self.process_compose_file(pod_name).await?;
        let content = fs::read_to_string(temp_compose_file.path()).await?;
        let compose_data: ComposeFile = serde_yaml::from_str(&content)
            .with_context(|| format!("Failed to parse compose file for '{}'", pod_name))?;

        let port_mappings: Vec<String> = compose_data.services.values()
            .filter_map(|s| s.ports.as_ref())
            .flatten()
            .map(|p| format!("-p={}", p))
            .collect();

        let memory_arg = format!("{}M", pod_config.mem);
        
        let mut command_args: Vec<&str> = vec![
            "pod", "create",
            "--name", &podman_pod_name,
            "--network", &self.backend_comm_network,
            "--cpus", &pod_config.cpu,
            "--memory", &memory_arg,
        ];
        
        let port_args_as_refs: Vec<&str> = port_mappings.iter().map(|s| s.as_str()).collect();
        command_args.extend(port_args_as_refs);

        self.run_command("podman", &command_args).await?;

        println!("✓ Successfully created pod '{}'.", podman_pod_name);
        Ok(())
    }

    pub async fn handle_down(&self, targets: &[String]) -> Result<()> {
        println!("\n=== Taking Down Pods and Services ===");

        let pod_targets = if targets.contains(&"all".to_string()) || targets.is_empty() {
            self.pods_config.keys().cloned().collect::<Vec<_>>()
        } else {
            targets.to_vec()
        };

        for pod_name in &pod_targets {
            println!("\n--- Taking Down Pod: {} ---", pod_name);
            self.take_down_pod_services(pod_name).await?;
            self.remove_pod_if_empty(pod_name).await?;
        }

        println!("\n✅ All targeted pods and services are down.");
        Ok(())
    }

    async fn take_down_pod_services(&self, pod_name: &str) -> Result<()> {
        let podman_pod_name = pod_name;
        println!("🚀 Taking down services for pod '{}'...", podman_pod_name);

        let pod_exists_output = Command::new("podman")
            .args(&["pod", "exists", &podman_pod_name])
            .output().await?;
        
        if !pod_exists_output.status.success() {
            println!("✓ Pod '{}' does not exist, skipping 'down' command.", podman_pod_name);
            return Ok(());
        }

        let temp_compose_file = self.process_compose_file(pod_name).await?;
        let compose_path_str = temp_compose_file.path().to_str()
            .context("Temporary compose file path is not valid UTF-8")?;

        self.run_command("podman-compose", &[
            "-f", compose_path_str,
            "-p", &podman_pod_name,
            "down"
        ]).await?;

        println!("✓ Services for pod '{}' are down.", podman_pod_name);
        Ok(())
    }

    async fn remove_pod_if_empty(&self, pod_name: &str) -> Result<()> {
        let podman_pod_name = pod_name;

        let pod_exists_output = Command::new("podman")
            .args(&["pod", "exists", &podman_pod_name])
            .output()
            .await?;

        if !pod_exists_output.status.success() {
            return Ok(());
        }

        println!("🔎 Checking if pod '{}' contains service containers...", podman_pod_name);

        let ps_output = Command::new("podman")
            .args(&[
                "ps",
                "-a",
                "--filter",
                &format!("pod={}", podman_pod_name),
                "--filter",
                "is-infra=false",
                "--format",
                "{{.ID}}",
            ])
            .output()
            .await?;

        let containers = String::from_utf8_lossy(&ps_output.stdout);
        if containers.trim().is_empty() {
            println!("✓ Pod '{}' contains no service containers. Removing...", podman_pod_name);
            self.run_command("podman", &["pod", "rm", "-f", &podman_pod_name]).await?;
            println!("✓ Pod '{}' removed.", podman_pod_name);
        } else {
            println!(
                "- Pod '{}' still has service containers, will not be removed. Containers found: {}",
                podman_pod_name,
                containers.trim()
            );
        }

        Ok(())
    }
}
