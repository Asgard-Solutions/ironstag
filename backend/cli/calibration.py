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
    
    dry_run = not args.execute
    
    if not dry_run:
        print_warning("This will build calibration curves from labeled data.")
        if ENVIRONMENT == 'production':
            confirm = input("Type 'YES' to confirm in production: ")
            if confirm != "YES":
                print_error("Aborted.")
                sys.exit(1)
    
    print_info(f"Dry run: {dry_run}")
    print()
    
    client = CalibrationClient()
    
    try:
        # First check maturity gates
        stats = client.get_label_stats()
        
        print(color("Pre-Build Check:", Colors.BOLD))
        print(f"  Total labels: {stats.get('total_labels', 0)}")
        print(f"  Weighted samples: {stats.get('total_weighted_samples', 0):.1f}")
        print()
        
        gates = stats.get('maturity_gates', {})
        print(color("Maturity Gates:", Colors.BOLD))
        global_min = gates.get('global_min_samples', False)
        global_weighted = gates.get('global_min_weighted', False)
        print(f"  Global min samples (500): {'✅ PASS' if global_min else '❌ NOT MET'}")
        print(f"  Global weighted samples: {'✅ PASS' if global_weighted else '❌ NOT MET'}")
        print()
        
        if not global_min and not dry_run:
            print_error("Cannot build curves: insufficient labeled data")
            print_info("Collect more labels before building curves (need 500+ samples)")
            sys.exit(1)
        
        # Build curves
        print_info("Building curves...")
        result = client.build_curves(dry_run=dry_run)
        
        print()
        print(color("Build Results:", Colors.BOLD))
        print(f"  Curves built: {result.get('curves_built', 0)}")
        print(f"  Mature curves: {result.get('curves_mature', 0)}")
        print(f"  Immature curves: {result.get('curves_immature', 0)}")
        print(f"  Labels processed: {result.get('total_labels_processed', 0)}")
        print(f"  Regions: {', '.join(result.get('regions_processed', [])) or 'None'}")
        print(f"  Duration: {result.get('duration_seconds', 0):.2f}s")
        print(f"  Version: {result.get('version', 'N/A')}")
        
        if result.get('errors'):
            print()
            print_warning("Errors:")
            for err in result['errors']:
                print(f"    - {err}")
        
        if dry_run:
            print()
            print_info("Dry run complete. Use --execute to persist curves.")
        else:
            print_success("Curves built and saved to database (inactive by default)")
            print_info("Use 'validate' and 'activate' commands to enable curves")
        
    except requests.exceptions.RequestException as e:
        print_error(f"API request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                detail = e.response.json().get('detail', str(e))
                print_error(f"  Detail: {detail}")
            except:
                pass
        sys.exit(1)


def cmd_validate(args):
    """Handle 'validate' command - validate a curve against gates."""
    print_header("Validate Calibration Curve")
    
    curve_id = args.curve_id
    print_info(f"Curve ID: {curve_id}")
    print()
    
    client = CalibrationClient()
    
    try:
        # Get curve details
        curve = client.get_curve_details(curve_id)
        
        print(color("Curve Details:", Colors.BOLD))
        print(f"  Type: {curve.get('curve_type', 'N/A')}")
        print(f"  Region: {curve.get('region_key', 'global')}")
        print(f"  Version: {curve.get('calibration_version', 'N/A')}")
        print(f"  Created: {curve.get('created_at', 'N/A')}")
        print(f"  Active: {curve.get('is_active', False)}")
        print()
        
        # Sample stats
        sample_count = curve.get('sample_count', 0)
        min_samples = curve.get('min_samples_required', 500)
        is_mature = curve.get('is_mature', False)
        
        print(color("Validation Gates:", Colors.BOLD))
        print(f"  Sample count: {sample_count} / {min_samples} required")
        print(f"  Maturity: {'✅ MATURE' if is_mature else '❌ IMMATURE'}")
        
        # Bin statistics
        bin_stats = curve.get('bin_stats', {})
        mature_bins = bin_stats.get('mature_bins', 0)
        total_bins = bin_stats.get('total_bins', 10)
        print(f"  Mature bins: {mature_bins} / {total_bins}")
        print()
        
        # Show bin details if requested
        if args.verbose:
            print(color("Bin Details:", Colors.BOLD))
            bins = curve.get('bins', [])
            for i, bin_data in enumerate(bins):
                min_conf = bin_data.get('min_confidence', 0)
                max_conf = bin_data.get('max_confidence', 100)
                samples = bin_data.get('sample_count', 0)
                calibrated = bin_data.get('calibrated_confidence', 0.5)
                status = '✅' if samples >= 20 else '⚠️'
                print(f"    [{min_conf}-{max_conf}%]: {samples} samples, cal={calibrated:.2%} {status}")
        
        # Activation recommendation
        print()
        if is_mature:
            print_success(f"Curve is ready for activation")
            print_info(f"Run: python -m cli.calibration activate --curve-id {curve_id} --confirm")
        else:
            print_warning("Curve not yet ready for activation")
            print_info(f"Need {min_samples - sample_count} more samples")
        
    except requests.exceptions.RequestException as e:
        print_error(f"API request failed: {e}")
        sys.exit(1)


def cmd_activate(args):
    """Handle 'activate' command - human-gated curve activation."""
    print_header("Human-Gated Curve Activation")
    
    if not args.confirm:
        print_error("Activation requires --confirm flag for safety.")
        print_info("This ensures intentional, human-reviewed activation.")
        sys.exit(1)
    
    curve_id = args.curve_id
    print_info(f"Curve ID: {curve_id}")
    print()
    
    client = CalibrationClient()
    
    try:
        # First validate the curve
        curve = client.get_curve_details(curve_id)
        
        if not curve.get('is_mature', False):
            print_error("Cannot activate: curve is not mature")
            print_info(f"Sample count: {curve.get('sample_count', 0)} / {curve.get('min_samples_required', 500)}")
            sys.exit(1)
        
        if curve.get('is_active', False):
            print_warning("Curve is already active")
            sys.exit(0)
        
        print(color("Activating Curve:", Colors.BOLD))
        print(f"  Type: {curve.get('curve_type', 'N/A')}")
        print(f"  Region: {curve.get('region_key', 'global')}")
        print(f"  Samples: {curve.get('sample_count', 0)}")
        print()
        
        if ENVIRONMENT == 'production':
            print_warning("PRODUCTION ENVIRONMENT - This will affect live users!")
            final_confirm = input("Type the curve ID to confirm: ")
            if final_confirm != curve_id:
                print_error("Curve ID mismatch. Aborted.")
                sys.exit(1)
        
        # Activate
        result = client.activate_curve(curve_id)
        
        if result.get('success'):
            print_success(f"Curve activated successfully!")
            print_info(f"Version: {result.get('calibration_version', 'N/A')}")
            print()
            print_info("New scans will now use this calibration curve.")
            print_info("Use 'recalibrate' command to update existing scans.")
        else:
            print_error(f"Activation failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
        
    except requests.exceptions.RequestException as e:
        print_error(f"API request failed: {e}")
        sys.exit(1)


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
    build_parser.add_argument("--scope", choices=["global", "region"], default="global", help="Curve scope (default: global)")
    build_parser.add_argument("--region", help="Region key (optional, for region-specific curves)")
    build_parser.add_argument("--dry-run", action="store_true", default=True, help="Preview without persisting (default)")
    build_parser.add_argument("--execute", action="store_true", help="Actually persist the curves")
    build_parser.set_defaults(func=cmd_build)
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate curve against activation gates")
    validate_parser.add_argument("--curve-id", required=True, help="Curve UUID to validate")
    validate_parser.add_argument("--verbose", "-v", action="store_true", help="Show bin-level details")
    validate_parser.set_defaults(func=cmd_validate)
    
    # Activate command
    activate_parser = subparsers.add_parser("activate", help="Human-gated curve activation")
    activate_parser.add_argument("--curve-id", required=True, help="Curve UUID to activate")
    activate_parser.add_argument("--confirm", action="store_true", help="Confirm activation (required)")
    activate_parser.set_defaults(func=cmd_activate)
    
    # Recalibrate command
    recalibrate_parser = subparsers.add_parser("recalibrate", help="Recalibrate existing scans with active curves")
    recalibrate_parser.add_argument("--region", help="Only recalibrate scans in this region")
    recalibrate_parser.add_argument("--dry-run", action="store_true", default=True, help="Preview without persisting (default)")
    recalibrate_parser.add_argument("--execute", action="store_true", help="Actually update scans")
    recalibrate_parser.set_defaults(func=cmd_recalibrate)
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
