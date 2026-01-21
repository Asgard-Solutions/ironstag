#!/usr/bin/env python3
"""
Phase 3 Adaptive Calibration CLI Tool

A safe, operator-friendly CLI for running Phase 3 calibration jobs.

Features:
- Dry-run by default (must explicitly opt-in to write)
- Environment safeguards (warns before production operations)
- Clear, actionable output
- All operations are ADVISORY ONLY

Usage:
    python phase3_admin.py status
    python phase3_admin.py drift --window 30
    python phase3_admin.py maturity
    python phase3_admin.py recommendations
    python phase3_admin.py run-drift --window 30 --execute
    python phase3_admin.py run-maturity --execute
    python phase3_admin.py run-recommendations --execute

Environment:
    PHASE3_API_URL - Override API base URL (default: http://localhost:8001/api)
    PHASE3_ENV     - Set to 'production' to enable production warnings
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any

try:
    import requests
except ImportError:
    print("❌ Error: 'requests' library required. Install with: pip install requests")
    sys.exit(1)


# ============================================================================
# CONFIGURATION
# ============================================================================

DEFAULT_API_URL = "http://localhost:8001/api"
API_URL = os.environ.get("PHASE3_API_URL", DEFAULT_API_URL)
ENVIRONMENT = os.environ.get("PHASE3_ENV", "development")

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


# ============================================================================
# API CLIENT
# ============================================================================

class Phase3Client:
    """Client for Phase 3 Admin API endpoints."""
    
    def __init__(self, base_url: str = API_URL):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Phase3-CLI/1.0"
        })
    
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make API request with error handling."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, timeout=60)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, timeout=120)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            # Parse response
            try:
                result = response.json()
            except json.JSONDecodeError:
                result = {"raw_response": response.text}
            
            # Add status code to result
            result["_status_code"] = response.status_code
            result["_success"] = response.status_code < 400
            
            return result
            
        except requests.exceptions.ConnectionError:
            return {
                "_status_code": 0,
                "_success": False,
                "error": f"Connection failed to {url}. Is the backend running?"
            }
        except requests.exceptions.Timeout:
            return {
                "_status_code": 0,
                "_success": False,
                "error": "Request timed out. The job may still be running."
            }
        except Exception as e:
            return {
                "_status_code": 0,
                "_success": False,
                "error": str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get Phase 3 system status."""
        return self._request("GET", "/admin/calibration/phase3/status")
    
    def get_drift(self, days: int = 30) -> Dict[str, Any]:
        """Get drift events summary."""
        return self._request("GET", f"/admin/calibration/drift?days={days}")
    
    def get_maturity(self) -> Dict[str, Any]:
        """Get region maturity summary."""
        return self._request("GET", "/admin/calibration/maturity")
    
    def get_recommendations(self, days: int = 30) -> Dict[str, Any]:
        """Get recommendations summary."""
        return self._request("GET", f"/admin/calibration/recommendations?days={days}")
    
    def run_drift_detection(self, window_days: int = 30, include_seasons: bool = True, dry_run: bool = True) -> Dict[str, Any]:
        """Run drift detection job."""
        return self._request("POST", "/admin/calibration/phase3/run-drift", {
            "dry_run": dry_run,
            "time_window_days": window_days,
            "include_seasons": include_seasons
        })
    
    def run_maturity_computation(self, dry_run: bool = True) -> Dict[str, Any]:
        """Run maturity computation job."""
        return self._request("POST", "/admin/calibration/phase3/run-maturity", {
            "dry_run": dry_run
        })
    
    def run_recommendations(self, dry_run: bool = True) -> Dict[str, Any]:
        """Run recommendations generation job."""
        return self._request("POST", "/admin/calibration/phase3/run-recommendations", {
            "dry_run": dry_run
        })


# ============================================================================
# OUTPUT FORMATTERS
# ============================================================================

def print_header(title: str):
    """Print a section header."""
    print()
    print(color("=" * 60, Colors.CYAN))
    print(color(f"  {title}", Colors.BOLD))
    print(color("=" * 60, Colors.CYAN))
    print()


def print_subheader(title: str):
    """Print a subsection header."""
    print()
    print(color(f"── {title} ──", Colors.BLUE))


def print_key_value(key: str, value: Any, indent: int = 0):
    """Print a key-value pair."""
    prefix = "  " * indent
    print(f"{prefix}{color(key + ':', Colors.DIM)} {value}")


def print_success(message: str):
    """Print success message."""
    print(color(f"✅ {message}", Colors.GREEN))


def print_warning(message: str):
    """Print warning message."""
    print(color(f"⚠️  {message}", Colors.WARNING))


def print_error(message: str):
    """Print error message."""
    print(color(f"❌ {message}", Colors.FAIL))


def print_info(message: str):
    """Print info message."""
    print(color(f"ℹ️  {message}", Colors.BLUE))


def format_status(data: Dict[str, Any]):
    """Format and print status response."""
    print_header("Phase 3 System Status")
    
    if not data.get("_success"):
        print_error(data.get("error", data.get("detail", "Unknown error")))
        return
    
    # Enabled status
    enabled = data.get("enabled", False)
    if enabled:
        print_success("Phase 3 Adaptive Calibration is ENABLED")
    else:
        print_warning("Phase 3 Adaptive Calibration is DISABLED")
        print_info("Set CALIBRATION_ADAPTIVE_ENABLED=true in .env to enable")
    
    # Jobs status
    print_subheader("Running Jobs")
    jobs = data.get("jobs", {})
    for job_name, running in jobs.items():
        status = color("RUNNING", Colors.WARNING) if running else color("idle", Colors.DIM)
        print(f"  • {job_name.replace('_', ' ').title()}: {status}")
    
    # Configuration
    print_subheader("Configuration")
    config = data.get("config", {})
    
    print("  Drift Thresholds:")
    print_key_value("Warning", f"{config.get('drift_warning_threshold', 0.08):.0%}", 2)
    print_key_value("Critical", f"{config.get('drift_critical_threshold', 0.12):.0%}", 2)
    print_key_value("Min Samples", config.get('drift_min_samples', 50), 2)
    
    print("  Maturity Thresholds:")
    thresholds = config.get("maturity_thresholds", {})
    print_key_value("Low", f"< {thresholds.get('medium', 300)} samples", 2)
    print_key_value("Medium", f"{thresholds.get('medium', 300)}-{thresholds.get('high', 500)} samples", 2)
    print_key_value("High", f"≥ {thresholds.get('high', 500)} samples", 2)
    
    print("  Trust Weights:")
    weights = config.get("trust_weights", {})
    for source, weight in sorted(weights.items(), key=lambda x: -x[1]):
        print_key_value(source.title(), f"{weight:.0%}", 2)


def format_drift(data: Dict[str, Any]):
    """Format and print drift summary."""
    print_header("Calibration Drift Summary")
    
    if not data.get("_success"):
        print_error(data.get("error", data.get("detail", "Unknown error")))
        return
    
    total = data.get("total_events", 0)
    by_severity = data.get("by_severity", {})
    by_region = data.get("by_region", {})
    events = data.get("events", [])
    
    print_key_value("Time Period", f"{data.get('time_period_days', 30)} days")
    print_key_value("Total Events", total)
    
    if total == 0:
        print_info("No drift events detected. Confidence is stable.")
        return
    
    # Severity breakdown
    print_subheader("By Severity")
    warnings = by_severity.get("warning", 0)
    criticals = by_severity.get("critical", 0)
    
    if criticals > 0:
        print(f"  {color(f'🔴 Critical: {criticals}', Colors.FAIL)}")
    if warnings > 0:
        print(f"  {color(f'🟡 Warning: {warnings}', Colors.WARNING)}")
    
    # Region breakdown
    if by_region:
        print_subheader("By Region")
        for region, count in sorted(by_region.items(), key=lambda x: -x[1]):
            print(f"  • {region}: {count} events")
    
    # Recent events (limit to 5)
    if events:
        print_subheader("Recent Events")
        for event in events[:5]:
            severity = event.get("severity", "unknown")
            severity_icon = "🔴" if severity == "critical" else "🟡"
            region = event.get("region_key", "unknown")
            conf_type = event.get("confidence_type", "unknown")
            drift = event.get("drift_percentage", 0)
            drift_str = f"{drift:+.1%}"
            expected = event.get("expected_accuracy", 0)
            observed = event.get("observed_accuracy", 0)
            
            print(f"  {severity_icon} [{region}] {conf_type}: {drift_str} drift")
            print(f"     Expected: {expected:.0%} → Observed: {observed:.0%}")
            if event.get("season_bucket"):
                print(f"     Season: {event['season_bucket']}")


def format_maturity(data: Dict[str, Any]):
    """Format and print maturity summary."""
    print_header("Region Maturity Summary")
    
    if not data.get("_success"):
        print_error(data.get("error", data.get("detail", "Unknown error")))
        return
    
    total = data.get("total_regions", 0)
    by_level = data.get("by_level", {})
    regions = data.get("regions", [])
    
    print_key_value("Total Regions", total)
    
    if total == 0:
        print_info("No regions with labeled data found.")
        return
    
    # Level breakdown
    print_subheader("By Maturity Level")
    high = by_level.get("high", 0)
    medium = by_level.get("medium", 0)
    low = by_level.get("low", 0)
    
    print(f"  {color(f'🟢 High: {high}', Colors.GREEN)}")
    print(f"  {color(f'🟡 Medium: {medium}', Colors.WARNING)}")
    print(f"  {color(f'🔴 Low: {low}', Colors.FAIL)}")
    
    # Region details
    if regions:
        print_subheader("Region Details")
        for region in regions:
            level = region.get("maturity_level", "unknown")
            level_icon = "🟢" if level == "high" else ("🟡" if level == "medium" else "🔴")
            name = region.get("region_key", "unknown")
            samples = region.get("labeled_sample_count", 0)
            diversity = region.get("label_source_diversity_score", 0)
            stability = region.get("stability_score", 0)
            
            print(f"  {level_icon} {name}")
            print(f"     Samples: {samples} | Diversity: {diversity:.2f} | Stability: {stability:.2f}")


def format_recommendations(data: Dict[str, Any]):
    """Format and print recommendations summary."""
    print_header("Model Action Recommendations")
    
    if not data.get("_success"):
        print_error(data.get("error", data.get("detail", "Unknown error")))
        return
    
    total = data.get("total_recommendations", 0)
    by_type = data.get("by_type", {})
    recommendations = data.get("recommendations", [])
    
    print_key_value("Time Period", f"{data.get('time_period_days', 30)} days")
    print_key_value("Total Recommendations", total)
    
    if total == 0:
        print_success("No action recommendations. System is operating normally.")
        return
    
    # Type breakdown
    print_subheader("By Type")
    type_descriptions = {
        "rebuild_calibration": "Rebuild calibration curves",
        "region_curve_update": "Update region-specific curves",
        "consider_retraining": "Consider model retraining",
        "investigate_data": "Investigate data quality"
    }
    
    for rec_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
        desc = type_descriptions.get(rec_type, rec_type)
        print(f"  • {desc}: {count}")
    
    # Recommendation details
    if recommendations:
        print_subheader("Action Items")
        for i, rec in enumerate(recommendations[:5], 1):
            severity = rec.get("severity", "warning")
            severity_icon = "🔴" if severity == "critical" else "🟡"
            rec_type = rec.get("recommendation_type", "unknown")
            region = rec.get("region_key") or "Global"
            desc = type_descriptions.get(rec_type, rec_type)
            
            print(f"  {i}. {severity_icon} {desc}")
            print(f"     Scope: {region}")
            
            metrics = rec.get("supporting_metrics", {})
            if metrics:
                for key, value in list(metrics.items())[:3]:
                    if isinstance(value, float):
                        value = f"{value:.2%}" if abs(value) < 1 else f"{value:.2f}"
                    print(f"     {key}: {value}")


def format_job_result(data: Dict[str, Any], job_name: str):
    """Format and print job execution result."""
    print_header(f"{job_name} Job Result")
    
    if not data.get("_success"):
        print_error(data.get("error", data.get("detail", "Unknown error")))
        return
    
    dry_run = data.get("dry_run", True)
    
    if dry_run:
        print_warning("DRY RUN - No changes were saved")
    else:
        print_success("EXECUTED - Changes have been saved")
    
    print()
    
    # Common fields
    print_key_value("Success", data.get("success", False))
    print_key_value("Duration", f"{data.get('duration_seconds', 0):.2f}s")
    
    # Job-specific fields
    if "events_detected" in data:
        print_key_value("Events Detected", data.get("events_detected", 0))
        print_key_value("Warnings", data.get("warnings", 0))
        print_key_value("Criticals", data.get("criticals", 0))
        if data.get("regions_analyzed"):
            print_key_value("Regions Analyzed", ", ".join(data["regions_analyzed"]))
    
    if "regions_computed" in data:
        print_key_value("Regions Computed", data.get("regions_computed", 0))
        print_key_value("High Maturity", data.get("high_maturity", 0))
        print_key_value("Medium Maturity", data.get("medium_maturity", 0))
        print_key_value("Low Maturity", data.get("low_maturity", 0))
    
    if "recommendations_generated" in data:
        print_key_value("Recommendations Generated", data.get("recommendations_generated", 0))
        if data.get("by_type"):
            print("  By Type:")
            for rec_type, count in data["by_type"].items():
                print_key_value(rec_type, count, 2)
    
    # Errors
    errors = data.get("errors", [])
    if errors:
        print_subheader("Errors/Warnings")
        for error in errors:
            print_warning(error)
    
    # Message
    if data.get("message"):
        print()
        print_info(data["message"])


# ============================================================================
# SAFETY CHECKS
# ============================================================================

def confirm_production_action(action: str) -> bool:
    """Prompt for confirmation before production actions."""
    if ENVIRONMENT.lower() != "production":
        return True
    
    print()
    print(color("⚠️  PRODUCTION ENVIRONMENT DETECTED", Colors.WARNING))
    print(f"You are about to: {action}")
    print()
    
    try:
        response = input("Type 'yes' to confirm: ").strip().lower()
        return response == "yes"
    except (KeyboardInterrupt, EOFError):
        print()
        return False


def check_phase3_enabled(client: Phase3Client) -> bool:
    """Check if Phase 3 is enabled and warn if not."""
    status = client.get_status()
    
    if not status.get("_success"):
        print_error(f"Cannot reach API: {status.get('error', 'Unknown error')}")
        return False
    
    if not status.get("enabled", False):
        print_warning("Phase 3 is currently DISABLED")
        print_info("Set CALIBRATION_ADAPTIVE_ENABLED=true in backend/.env to enable")
        return False
    
    return True


# ============================================================================
# CLI COMMANDS
# ============================================================================

def cmd_status(args):
    """Handle 'status' command."""
    client = Phase3Client()
    result = client.get_status()
    format_status(result)


def cmd_drift(args):
    """Handle 'drift' command."""
    client = Phase3Client()
    
    if not check_phase3_enabled(client):
        return
    
    result = client.get_drift(days=args.window)
    format_drift(result)


def cmd_maturity(args):
    """Handle 'maturity' command."""
    client = Phase3Client()
    
    if not check_phase3_enabled(client):
        return
    
    result = client.get_maturity()
    format_maturity(result)


def cmd_recommendations(args):
    """Handle 'recommendations' command."""
    client = Phase3Client()
    
    if not check_phase3_enabled(client):
        return
    
    result = client.get_recommendations(days=args.window)
    format_recommendations(result)


def cmd_run_drift(args):
    """Handle 'run-drift' command."""
    client = Phase3Client()
    
    if not check_phase3_enabled(client):
        return
    
    dry_run = not args.execute
    
    if not dry_run:
        if not confirm_production_action("Run drift detection and SAVE results to database"):
            print_info("Cancelled.")
            return
    
    print_info(f"Running drift detection (dry_run={dry_run}, window={args.window} days)...")
    result = client.run_drift_detection(
        window_days=args.window,
        include_seasons=not args.no_seasons,
        dry_run=dry_run
    )
    format_job_result(result, "Drift Detection")


def cmd_run_maturity(args):
    """Handle 'run-maturity' command."""
    client = Phase3Client()
    
    if not check_phase3_enabled(client):
        return
    
    dry_run = not args.execute
    
    if not dry_run:
        if not confirm_production_action("Run maturity computation and SAVE results to database"):
            print_info("Cancelled.")
            return
    
    print_info(f"Running maturity computation (dry_run={dry_run})...")
    result = client.run_maturity_computation(dry_run=dry_run)
    format_job_result(result, "Maturity Computation")


def cmd_run_recommendations(args):
    """Handle 'run-recommendations' command."""
    client = Phase3Client()
    
    if not check_phase3_enabled(client):
        return
    
    dry_run = not args.execute
    
    if not dry_run:
        if not confirm_production_action("Run recommendation generation and SAVE results to database"):
            print_info("Cancelled.")
            return
    
    print_info(f"Running recommendation generation (dry_run={dry_run})...")
    result = client.run_recommendations(dry_run=dry_run)
    format_job_result(result, "Recommendation Generation")


def cmd_run_all(args):
    """Handle 'run-all' command - runs all jobs in sequence."""
    client = Phase3Client()
    
    if not check_phase3_enabled(client):
        return
    
    dry_run = not args.execute
    
    if not dry_run:
        if not confirm_production_action("Run ALL Phase 3 jobs and SAVE results to database"):
            print_info("Cancelled.")
            return
    
    print_header("Running All Phase 3 Jobs")
    
    # 1. Drift Detection
    print_info(f"[1/3] Running drift detection...")
    drift_result = client.run_drift_detection(
        window_days=args.window,
        include_seasons=True,
        dry_run=dry_run
    )
    
    if drift_result.get("_success"):
        print_success(f"Drift: {drift_result.get('events_detected', 0)} events detected")
    else:
        print_error(f"Drift: {drift_result.get('error', 'Failed')}")
    
    # 2. Maturity Computation
    print_info(f"[2/3] Running maturity computation...")
    maturity_result = client.run_maturity_computation(dry_run=dry_run)
    
    if maturity_result.get("_success"):
        print_success(f"Maturity: {maturity_result.get('regions_computed', 0)} regions computed")
    else:
        print_error(f"Maturity: {maturity_result.get('error', 'Failed')}")
    
    # 3. Recommendations
    print_info(f"[3/3] Running recommendation generation...")
    rec_result = client.run_recommendations(dry_run=dry_run)
    
    if rec_result.get("_success"):
        print_success(f"Recommendations: {rec_result.get('recommendations_generated', 0)} generated")
    else:
        print_error(f"Recommendations: {rec_result.get('error', 'Failed')}")
    
    # Summary
    print_header("Summary")
    if dry_run:
        print_warning("DRY RUN - No changes were saved")
        print_info("Use --execute flag to save results")
    else:
        print_success("All jobs completed and results saved")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Phase 3 Adaptive Calibration CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s status                    # Check system status
  %(prog)s drift                     # View drift events
  %(prog)s maturity                  # View region maturity
  %(prog)s recommendations           # View action recommendations
  
  %(prog)s run-drift                 # Preview drift detection (dry run)
  %(prog)s run-drift --execute       # Run drift detection and save
  %(prog)s run-all --execute         # Run all jobs and save

Environment Variables:
  PHASE3_API_URL  - Override API base URL (default: http://localhost:8001/api)
  PHASE3_ENV      - Set to 'production' for production safeguards
        """
    )
    
    parser.add_argument(
        "--api-url",
        default=API_URL,
        help=f"API base URL (default: {API_URL})"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted text"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check Phase 3 system status")
    status_parser.set_defaults(func=cmd_status)
    
    # Drift command
    drift_parser = subparsers.add_parser("drift", help="View drift events summary")
    drift_parser.add_argument("--window", type=int, default=30, help="Time window in days (default: 30)")
    drift_parser.set_defaults(func=cmd_drift)
    
    # Maturity command
    maturity_parser = subparsers.add_parser("maturity", help="View region maturity summary")
    maturity_parser.set_defaults(func=cmd_maturity)
    
    # Recommendations command
    rec_parser = subparsers.add_parser("recommendations", help="View action recommendations")
    rec_parser.add_argument("--window", type=int, default=30, help="Time window in days (default: 30)")
    rec_parser.set_defaults(func=cmd_recommendations)
    
    # Run-drift command
    run_drift_parser = subparsers.add_parser("run-drift", help="Run drift detection job")
    run_drift_parser.add_argument("--window", type=int, default=30, help="Time window in days (default: 30)")
    run_drift_parser.add_argument("--no-seasons", action="store_true", help="Disable seasonal segmentation")
    run_drift_parser.add_argument("--execute", action="store_true", help="Actually save results (default is dry run)")
    run_drift_parser.set_defaults(func=cmd_run_drift)
    
    # Run-maturity command
    run_maturity_parser = subparsers.add_parser("run-maturity", help="Run maturity computation job")
    run_maturity_parser.add_argument("--execute", action="store_true", help="Actually save results (default is dry run)")
    run_maturity_parser.set_defaults(func=cmd_run_maturity)
    
    # Run-recommendations command
    run_rec_parser = subparsers.add_parser("run-recommendations", help="Run recommendation generation job")
    run_rec_parser.add_argument("--execute", action="store_true", help="Actually save results (default is dry run)")
    run_rec_parser.set_defaults(func=cmd_run_recommendations)
    
    # Run-all command
    run_all_parser = subparsers.add_parser("run-all", help="Run all Phase 3 jobs in sequence")
    run_all_parser.add_argument("--window", type=int, default=30, help="Time window in days (default: 30)")
    run_all_parser.add_argument("--execute", action="store_true", help="Actually save results (default is dry run)")
    run_all_parser.set_defaults(func=cmd_run_all)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    # Override API URL if provided
    api_url = args.api_url
    
    # Print banner
    print()
    print(color("╔══════════════════════════════════════════════════════════╗", Colors.CYAN))
    print(color("║       Phase 3 Adaptive Calibration CLI Tool              ║", Colors.CYAN))
    print(color("║       ADVISORY ONLY - No Automatic Changes               ║", Colors.CYAN))
    print(color("╚══════════════════════════════════════════════════════════╝", Colors.CYAN))
    print(f"  API: {api_url}")
    print(f"  Environment: {ENVIRONMENT}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run command
    args.func(args)
    
    print()


if __name__ == "__main__":
    main()
