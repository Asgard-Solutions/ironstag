#!/usr/bin/env python3
"""
Empirical Calibration CLI Tool (Phase 2)

A safe, operator-friendly CLI for managing empirical calibration.

Features:
- Label inspection and statistics
- Curve building with dry-run support
- Human-gated activation (objective validation gates)
- Comprehensive status reporting

Usage:
    python -m cli.calibration labels --region midwest --since 2024-01-01
    python -m cli.calibration build --scope region --region midwest --dry-run
    python -m cli.calibration validate --curve-id <uuid>
    python -m cli.calibration activate --curve-id <uuid> --confirm
    python -m cli.calibration status

Environment:
    CALIBRATION_API_URL - Override API base URL (default: http://localhost:8001/api)
    CALIBRATION_ENV     - Set to 'production' to enable production warnings
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

try:
    import requests
except ImportError:
    print("❌ Error: 'requests' library required. Install with: pip install requests")
    sys.exit(1)


# ============================================================================
# CONFIGURATION
# ============================================================================

DEFAULT_API_URL = "http://localhost:8001/api"
API_URL = os.environ.get("CALIBRATION_API_URL", DEFAULT_API_URL)
ENVIRONMENT = os.environ.get("CALIBRATION_ENV", "development")

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


def color(text: str, color_code: str) -> str:
    """Apply color to text if terminal supports it."""
    if sys.stdout.isatty():
        return f"{color_code}{text}{Colors.ENDC}"
    return text


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{color('═' * 60, Colors.CYAN)}")
    print(color(f"  {text}", Colors.BOLD))
    print(f"{color('═' * 60, Colors.CYAN)}\n")


def print_warning(text: str):
    """Print a warning message."""
    print(color(f"⚠️  {text}", Colors.WARNING))


def print_success(text: str):
    """Print a success message."""
    print(color(f"✅ {text}", Colors.GREEN))


def print_error(text: str):
    """Print an error message."""
    print(color(f"❌ {text}", Colors.FAIL))


def print_info(text: str):
    """Print an info message."""
    print(color(f"ℹ️  {text}", Colors.BLUE))


# ============================================================================
# API CLIENT
# ============================================================================

class CalibrationClient:
    """Client for Calibration Admin API endpoints."""
    
    def __init__(self, base_url: str = API_URL):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
        })
    
    def get_labels(self, region: Optional[str] = None, since: Optional[str] = None,
                   label_type: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """Get label statistics and data."""
        params = {"limit": limit}
        if region:
            params["region"] = region
        if since:
            params["since"] = since
        if label_type:
            params["label_type"] = label_type
        
        response = self.session.get(f"{self.base_url}/admin/calibration/labels", params=params)
        response.raise_for_status()
        return response.json()
    
    def get_label_stats(self, region: Optional[str] = None) -> Dict[str, Any]:
        """Get label statistics summary."""
        params = {}
        if region:
            params["region"] = region
        
        response = self.session.get(f"{self.base_url}/admin/calibration/labels/stats", params=params)
        response.raise_for_status()
        return response.json()
    
    def get_curves_summary(self) -> Dict[str, Any]:
        """Get calibration curves summary."""
        response = self.session.get(f"{self.base_url}/admin/calibration/curves")
        response.raise_for_status()
        return response.json()
    
    def get_curve_details(self, curve_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific curve."""
        response = self.session.get(f"{self.base_url}/admin/calibration/curves/{curve_id}")
        response.raise_for_status()
        return response.json()
    
    def get_status(self) -> Dict[str, Any]:
        """Get calibration system status."""
        response = self.session.get(f"{self.base_url}/admin/calibration/status")
        response.raise_for_status()
        return response.json()
    
    def get_jobs_status(self) -> Dict[str, Any]:
        """Get calibration jobs status."""
        response = self.session.get(f"{self.base_url}/admin/calibration/jobs/status")
        response.raise_for_status()
        return response.json()
    
    def build_curves(self, dry_run: bool = True) -> Dict[str, Any]:
        """Build calibration curves from labeled data."""
        response = self.session.post(
            f"{self.base_url}/admin/calibration/build-curves",
            json={"dry_run": dry_run}
        )
        response.raise_for_status()
        return response.json()
    
    def activate_curve(self, curve_id: str) -> Dict[str, Any]:
        """Activate a calibration curve."""
        response = self.session.post(
            f"{self.base_url}/admin/calibration/activate-curve",
            json={"curve_id": curve_id}
        )
        response.raise_for_status()
        return response.json()
    
    def deactivate_curve(self, curve_id: str) -> Dict[str, Any]:
        """Deactivate a calibration curve."""
        response = self.session.post(f"{self.base_url}/admin/calibration/deactivate-curve/{curve_id}")
        response.raise_for_status()
        return response.json()
    
    def recalibrate_scans(self, dry_run: bool = True, region: Optional[str] = None) -> Dict[str, Any]:
        """Recalibrate existing scans using active curves."""
        payload = {"dry_run": dry_run}
        if region:
            payload["region"] = region
        response = self.session.post(
            f"{self.base_url}/admin/calibration/recalibrate-scans",
            json=payload
        )
        response.raise_for_status()
        return response.json()


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

def cmd_labels(args):
    """Handle 'labels' command - inspect label data."""
    print_header("Scan Labels Inspection")
    
    client = CalibrationClient()
    
    try:
        # Get label statistics
        stats = client.get_label_stats(region=args.region)
        
        print(color("Label Statistics:", Colors.BOLD))
        print(f"  Total labels: {stats.get('total_labels', 0)}")
        print(f"  Exact age labels (strong): {stats.get('exact_age_count', 0)}")
        print(f"  Categorical labels (weak): {stats.get('categorical_count', 0)}")
        print()
        
        # By region breakdown
        if 'by_region' in stats:
            print(color("By Region:", Colors.BOLD))
            for region, count in stats['by_region'].items():
                print(f"  {region}: {count} labels")
            print()
        
        # By error bucket
        if 'by_error_bucket' in stats:
            print(color("By Error Bucket:", Colors.BOLD))
            for bucket, count in stats['by_error_bucket'].items():
                print(f"  {bucket}: {count} labels")
            print()
        
        # Get recent labels if requested
        if args.show_recent:
            labels_data = client.get_labels(
                region=args.region,
                since=args.since,
                limit=args.limit or 20
            )
            
            labels = labels_data.get('labels', [])
            if labels:
                print(color(f"Recent Labels ({len(labels)}):", Colors.BOLD))
                for label in labels[:10]:
                    label_type = label.get('label_type', 'unknown')
                    weight = label.get('effective_weight', label.get('label_weight', 0))
                    error = label.get('error_bucket', 'N/A')
                    print(f"  [{label['id'][:8]}] type={label_type}, weight={weight:.2f}, error={error}")
        
        print_success("Labels inspection complete")
        
    except requests.exceptions.RequestException as e:
        print_error(f"API request failed: {e}")
        sys.exit(1)


def cmd_status(args):
    """Handle 'status' command - show calibration system status."""
    print_header("Calibration System Status")
    
    client = CalibrationClient()
    
    try:
        status = client.get_status()
        
        print(color("System Status:", Colors.BOLD))
        print(f"  Status: {status.get('status', 'unknown')}")
        print(f"  Active Version: {status.get('active_version', 'N/A')}")
        print()
        
        # Feature flags
        flags = status.get('feature_flags', {})
        print(color("Feature Flags:", Colors.BOLD))
        print(f"  Calibration Enabled: {flags.get('calibration_enabled', False)}")
        print(f"  Region Enabled: {flags.get('region_enabled', False)}")
        print(f"  Curves Enabled: {flags.get('curves_enabled', False)}")
        print()
        
        # Get curves summary
        curves = client.get_curves_summary()
        active_curves = [c for c in curves.get('curves', []) if c.get('is_active')]
        
        print(color("Calibration Curves:", Colors.BOLD))
        print(f"  Total curves: {len(curves.get('curves', []))}")
        print(f"  Active curves: {len(active_curves)}")
        
        if active_curves:
            print("\n  Active Curves:")
            for curve in active_curves:
                print(f"    - {curve.get('curve_type')} ({curve.get('region_key', 'global')}): {curve.get('sample_count', 0)} samples")
        
        print_success("Status check complete")
        
    except requests.exceptions.RequestException as e:
        print_error(f"API request failed: {e}")
        sys.exit(1)


def cmd_build(args):
    """Handle 'build' command - build calibration curves."""
    print_header("Build Calibration Curves")
    
    if not args.dry_run:
        print_warning("This will build and potentially activate calibration curves.")
        if ENVIRONMENT == 'production':
            print_error("Production environment detected. Use --dry-run first.")
            sys.exit(1)
    
    print_info(f"Scope: {args.scope}")
    if args.region:
        print_info(f"Region: {args.region}")
    print_info(f"Dry run: {args.dry_run}")
    print()
    
    # TODO: Implement curve building via API
    print_warning("Curve building not yet implemented. Coming in Phase 2.")


def cmd_validate(args):
    """Handle 'validate' command - validate a curve against gates."""
    print_header("Validate Calibration Curve")
    
    print_info(f"Curve ID: {args.curve_id}")
    print()
    
    # TODO: Implement curve validation via API
    print_warning("Curve validation not yet implemented. Coming in Phase 2.")


def cmd_activate(args):
    """Handle 'activate' command - human-gated curve activation."""
    print_header("Human-Gated Curve Activation")
    
    if not args.confirm:
        print_error("Activation requires --confirm flag for safety.")
        sys.exit(1)
    
    print_info(f"Curve ID: {args.curve_id}")
    print()
    
    # TODO: Implement curve activation via API
    print_warning("Curve activation not yet implemented. Coming in Phase 2.")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Empirical Calibration CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m cli.calibration labels --region midwest
  python -m cli.calibration labels --since 2024-01-01 --show-recent
  python -m cli.calibration status
  python -m cli.calibration build --scope global --dry-run
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Labels command
    labels_parser = subparsers.add_parser("labels", help="Inspect label data and statistics")
    labels_parser.add_argument("--region", help="Filter by region (e.g., midwest, southeast)")
    labels_parser.add_argument("--since", help="Filter labels since date (YYYY-MM-DD)")
    labels_parser.add_argument("--limit", type=int, default=100, help="Max labels to retrieve")
    labels_parser.add_argument("--show-recent", action="store_true", help="Show recent individual labels")
    labels_parser.set_defaults(func=cmd_labels)
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show calibration system status")
    status_parser.set_defaults(func=cmd_status)
    
    # Build command
    build_parser = subparsers.add_parser("build", help="Build calibration curves")
    build_parser.add_argument("--scope", choices=["global", "region"], required=True, help="Curve scope")
    build_parser.add_argument("--region", help="Region key (required if scope=region)")
    build_parser.add_argument("--dry-run", action="store_true", default=True, help="Preview without persisting")
    build_parser.add_argument("--execute", action="store_true", help="Actually persist the curve")
    build_parser.set_defaults(func=cmd_build)
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate curve against activation gates")
    validate_parser.add_argument("--curve-id", required=True, help="Curve UUID to validate")
    validate_parser.set_defaults(func=cmd_validate)
    
    # Activate command
    activate_parser = subparsers.add_parser("activate", help="Human-gated curve activation")
    activate_parser.add_argument("--curve-id", required=True, help="Curve UUID to activate")
    activate_parser.add_argument("--confirm", action="store_true", help="Confirm activation (required)")
    activate_parser.set_defaults(func=cmd_activate)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    # Handle --execute flag for build
    if hasattr(args, 'execute') and args.execute:
        args.dry_run = False
    
    args.func(args)


if __name__ == "__main__":
    main()
