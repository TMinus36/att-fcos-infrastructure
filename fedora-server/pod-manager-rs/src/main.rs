use clap::{Parser, Subcommand};
mod manager;
use manager::PodManager;

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Bring up pods and services
    Up { 
        /// Target pod(s) or service(s) in pod/service format. Defaults to all pods.
        #[arg(default_value = "all")]
        targets: Vec<String> 
    },
    /// Take down pods and services
    Down { 
        /// Target pod(s) or service(s) in pod/service format. Defaults to all pods.
        #[arg(default_value = "all")]
        targets: Vec<String> 
    },
    /// Restart pods and services
    Restart { 
        /// Target pod(s) or service(s) in pod/service format. Defaults to all pods.
        #[arg(default_value = "all")]
        targets: Vec<String> 
    },
    /// Get the status of pods and services
    Status { 
        /// Target pod(s) or service(s) in pod/service format. Defaults to all pods.
        #[arg(default_value = "all")]
        targets: Vec<String> 
    },
    /// Validate all compose files
    Validate {},
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();

        let current_path = std::env::current_dir().expect("Failed to get current directory");
    let base_path = current_path.parent().expect("Failed to get project root").to_path_buf();
    let manager = PodManager::new(&base_path);

    manager.check_system_prerequisites().await?;
    manager.ensure_network_exists(&manager.backend_comm_network).await?;

    println!("Initialized PodManager with base path: {:?}", manager.base_path);
    println!("Command received: {:?}", cli.command);

    // Match on the command and call the appropriate handler function
    match &cli.command {
        Commands::Up { targets } => {
            manager.handle_up(targets).await?;
        }
        Commands::Down { targets } => {
            manager.handle_down(targets).await?;
        }
        Commands::Restart { targets } => {
            println!("Action: Restart, Targets: {:?}", targets);
        }
        Commands::Status { targets } => {
            println!("Action: Status, Targets: {:?}", targets);
        }
        Commands::Validate {} => {
            manager.handle_validate().await?;
        }
    }

    Ok(())
}
