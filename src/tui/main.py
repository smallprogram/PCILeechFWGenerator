"""
Main TUI Application

The main entry point for the PCILeech Firmware Generator TUI.
"""

import asyncio
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Button, DataTable, ProgressBar, Log
from textual.reactive import reactive
from textual.message import Message
from textual import events
from typing import Optional

from .core.device_manager import DeviceManager
from .core.config_manager import ConfigManager
from .core.build_orchestrator import BuildOrchestrator
from .core.status_monitor import StatusMonitor
from .models.device import PCIDevice
from .models.config import BuildConfiguration
from .models.progress import BuildProgress


class PCILeechTUI(App):
    """Main TUI application for PCILeech firmware generation"""

    CSS_PATH = "styles/main.tcss"
    TITLE = "PCILeech Firmware Generator"
    SUB_TITLE = "Interactive firmware generation for PCIe devices"

    # Reactive attributes
    selected_device: reactive[Optional[PCIDevice]] = reactive(None)
    current_config: reactive[BuildConfiguration] = reactive(BuildConfiguration())
    build_progress: reactive[Optional[BuildProgress]] = reactive(None)

    def __init__(self):
        super().__init__()

        # Core services
        self.device_manager = DeviceManager()
        self.config_manager = ConfigManager()
        self.build_orchestrator = BuildOrchestrator()
        self.status_monitor = StatusMonitor()

        # State
        self._devices = []
        self._system_status = {}

    def compose(self) -> ComposeResult:
        """Create the main UI layout"""
        yield Header()

        with Container(id="main-container"):
            with Horizontal(id="top-section"):
                # Device Selection Panel
                with Vertical(id="device-panel", classes="panel"):
                    yield Static("📡 PCIe Device Selection", classes="panel-title")
                    yield DataTable(id="device-table")
                    with Horizontal(classes="button-row"):
                        yield Button("Refresh", id="refresh-devices", variant="primary")
                        yield Button("Details", id="device-details", disabled=True)

                # Configuration Panel
                with Vertical(id="config-panel", classes="panel"):
                    yield Static("⚙️ Build Configuration", classes="panel-title")
                    yield Static("Board Type: 75t", id="board-type")
                    yield Static("Device Type: generic", id="device-type")
                    yield Static("Advanced Features: Enabled", id="advanced-features")
                    with Horizontal(classes="button-row"):
                        yield Button("Configure", id="configure", variant="primary")
                        yield Button("Load Profile", id="load-profile")
                        yield Button("Save Profile", id="save-profile")

            with Horizontal(id="middle-section"):
                # Build Progress Panel
                with Vertical(id="build-panel", classes="panel"):
                    yield Static("🔨 Build Progress", classes="panel-title")
                    yield Static("Status: Ready to Build", id="build-status")
                    yield ProgressBar(total=100, id="build-progress")
                    yield Static("Progress: 0% (0/6 stages)", id="progress-text")
                    yield Static(
                        "Resources: CPU: 0% | Memory: 0GB | Disk: 0GB free",
                        id="resource-usage",
                    )
                    with Horizontal(classes="button-row"):
                        yield Button(
                            "▶ Start Build",
                            id="start-build",
                            variant="success",
                            disabled=True,
                        )
                        yield Button("⏸ Pause", id="pause-build", disabled=True)
                        yield Button("⏹ Stop", id="stop-build", disabled=True)
                        yield Button("📋 View Logs", id="view-logs")

            with Horizontal(id="bottom-section"):
                # System Status Panel
                with Vertical(id="status-panel", classes="panel"):
                    yield Static("📊 System Status", classes="panel-title")
                    yield Static("🐳 Podman: Checking...", id="podman-status")
                    yield Static("⚡ Vivado: Checking...", id="vivado-status")
                    yield Static("🔌 USB Devices: Checking...", id="usb-status")
                    yield Static("💾 Disk Space: Checking...", id="disk-status")
                    yield Static("🔒 Root Access: Checking...", id="root-status")

                # Quick Actions Panel
                with Vertical(id="actions-panel", classes="panel"):
                    yield Static("🚀 Quick Actions", classes="panel-title")
                    yield Button(
                        "🔍 Scan Devices", id="scan-devices", variant="primary"
                    )
                    yield Button("📁 Open Output Dir", id="open-output")
                    yield Button("📊 View Last Build Report", id="view-report")
                    yield Button("⚙️ Advanced Settings", id="advanced-settings")
                    yield Button("📖 Documentation", id="documentation")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the application"""
        # Set up the device table
        device_table = self.query_one("#device-table", DataTable)
        device_table.add_columns("Status", "BDF", "Device", "Driver", "IOMMU")

        # Start background tasks
        self.call_after_refresh(self._initialize_app)

    async def _initialize_app(self) -> None:
        """Initialize the application with data"""
        # Load default configuration profiles
        self.config_manager.create_default_profiles()

        # Start system status monitoring
        asyncio.create_task(self._monitor_system_status())

        # Initial device scan
        await self._scan_devices()

        # Update UI with current config
        self._update_config_display()

    async def _scan_devices(self) -> None:
        """Scan for PCIe devices"""
        try:
            self._devices = await self.device_manager.scan_devices()
            self._update_device_table()

            # Update device count in title
            device_count = len(self._devices)
            device_panel = self.query_one("#device-panel .panel-title", Static)
            device_panel.update(f"📡 PCIe Devices Found: {device_count}")

        except Exception as e:
            self.notify(f"Failed to scan devices: {e}", severity="error")

    def _update_device_table(self) -> None:
        """Update the device table with current devices"""
        device_table = self.query_one("#device-table", DataTable)
        device_table.clear()

        for device in self._devices:
            device_table.add_row(
                device.status_indicator,
                device.bdf,
                f"{device.vendor_name} {device.device_name}"[:40],
                device.driver or "none",
                device.iommu_group,
                key=device.bdf,
            )

    def _update_config_display(self) -> None:
        """Update configuration display"""
        config = self.current_config

        self.query_one("#board-type", Static).update(f"Board Type: {config.board_type}")
        self.query_one("#device-type", Static).update(
            f"Device Type: {config.device_type}"
        )

        features = "Enabled" if config.is_advanced else "Basic"
        self.query_one("#advanced-features", Static).update(
            f"Advanced Features: {features}"
        )

    async def _monitor_system_status(self) -> None:
        """Monitor system status continuously"""
        while True:
            try:
                self._system_status = await self.status_monitor.get_system_status()
                self._update_status_display()
                await asyncio.sleep(5)  # Update every 5 seconds
            except Exception as e:
                self.notify(f"Status monitoring error: {e}", severity="warning")
                await asyncio.sleep(10)  # Retry after 10 seconds on error

    def _update_status_display(self) -> None:
        """Update system status display"""
        status = self._system_status

        # Podman status
        podman = status.get("podman", {})
        podman_text = "🐳 Podman: " + (
            "Ready" if podman.get("status") == "ready" else "Not Available"
        )
        self.query_one("#podman-status", Static).update(podman_text)

        # Vivado status
        vivado = status.get("vivado", {})
        if vivado.get("status") == "detected":
            vivado_text = f"⚡ Vivado: {vivado.get('version', 'Unknown')} Detected"
        else:
            vivado_text = "⚡ Vivado: Not Detected"
        self.query_one("#vivado-status", Static).update(vivado_text)

        # USB devices
        usb = status.get("usb_devices", {})
        usb_count = usb.get("count", 0)
        usb_text = f"🔌 USB Devices: {usb_count} Found"
        self.query_one("#usb-status", Static).update(usb_text)

        # Disk space
        disk = status.get("disk_space", {})
        if "free_gb" in disk:
            disk_text = f"💾 Disk Space: {disk['free_gb']} GB Free"
        else:
            disk_text = "💾 Disk Space: Unknown"
        self.query_one("#disk-status", Static).update(disk_text)

        # Root access
        root = status.get("root_access", {})
        root_text = "🔒 Root Access: " + (
            "Available" if root.get("available") else "Required"
        )
        self.query_one("#root-status", Static).update(root_text)

    def _update_build_progress(self) -> None:
        """Update build progress display"""
        if not self.build_progress:
            return

        progress = self.build_progress

        # Update status
        self.query_one("#build-status", Static).update(
            f"Status: {progress.status_text}"
        )

        # Update progress bar
        progress_bar = self.query_one("#build-progress", ProgressBar)
        progress_bar.progress = progress.overall_progress

        # Update progress text
        self.query_one("#progress-text", Static).update(progress.progress_bar_text)

        # Update resource usage
        if progress.resource_usage:
            cpu = progress.resource_usage.get("cpu", 0)
            memory = progress.resource_usage.get("memory", 0)
            disk = progress.resource_usage.get("disk_free", 0)
            resource_text = f"Resources: CPU: {cpu:.1f}% | Memory: {memory:.1f}GB | Disk: {disk:.1f}GB free"
            self.query_one("#resource-usage", Static).update(resource_text)

    # Event handlers
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events"""
        button_id = event.button.id

        if button_id == "refresh-devices" or button_id == "scan-devices":
            await self._scan_devices()

        elif button_id == "start-build":
            await self._start_build()

        elif button_id == "stop-build":
            await self._stop_build()

        elif button_id == "configure":
            self.notify("Configuration dialog not yet implemented", severity="info")

        elif button_id == "open-output":
            import subprocess

            subprocess.run(["xdg-open", "output"], check=False)

        elif button_id == "documentation":
            self.notify("Opening documentation...", severity="info")

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle device table row selection"""
        device_table = event.data_table
        row_key = event.row_key

        # Find selected device
        selected_device = None
        for device in self._devices:
            if device.bdf == row_key:
                selected_device = device
                break

        if selected_device:
            self.selected_device = selected_device

            # Enable/disable buttons based on selection
            self.query_one("#device-details", Button).disabled = False
            self.query_one("#start-build", Button).disabled = (
                not selected_device.is_suitable
            )

            self.notify(f"Selected device: {selected_device.bdf}", severity="info")

    async def _start_build(self) -> None:
        """Start the build process"""
        if not self.selected_device:
            self.notify("Please select a device first", severity="error")
            return

        if self.build_orchestrator.is_building():
            self.notify("Build already in progress", severity="warning")
            return

        try:
            # Update button states
            self.query_one("#start-build", Button).disabled = True
            self.query_one("#stop-build", Button).disabled = False

            # Start build with progress callback
            success = await self.build_orchestrator.start_build(
                self.selected_device, self.current_config, self._on_build_progress
            )

            if success:
                self.notify("Build completed successfully!", severity="success")
            else:
                self.notify("Build was cancelled", severity="warning")

        except Exception as e:
            self.notify(f"Build failed: {e}", severity="error")
        finally:
            # Reset button states
            self.query_one("#start-build", Button).disabled = False
            self.query_one("#stop-build", Button).disabled = True

    async def _stop_build(self) -> None:
        """Stop the build process"""
        await self.build_orchestrator.cancel_build()
        self.notify("Build cancelled", severity="info")

    def _on_build_progress(self, progress: BuildProgress) -> None:
        """Handle build progress updates"""
        self.build_progress = progress
        self.call_after_refresh(self._update_build_progress)

    # Reactive watchers
    def watch_selected_device(self, device: Optional[PCIDevice]) -> None:
        """React to device selection changes"""
        if device:
            self.sub_title = f"Selected: {device.bdf} - {device.display_name}"
        else:
            self.sub_title = "Interactive firmware generation for PCIe devices"

    def watch_build_progress(self, progress: Optional[BuildProgress]) -> None:
        """React to build progress changes"""
        if progress:
            self._update_build_progress()


if __name__ == "__main__":
    app = PCILeechTUI()
    app.run()
