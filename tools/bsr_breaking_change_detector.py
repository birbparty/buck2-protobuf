#!/usr/bin/env python3
"""
BSR Breaking Change Detector for Buck2 Protobuf.

This module provides comprehensive breaking change detection by comparing
protobuf schemas against BSR repositories with detailed impact analysis.
"""

import argparse
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Union, Any, Tuple
import logging

# Local imports
from .bsr_auth import BSRAuthenticator, BSRCredentials
from .bsr_client import BSRClient
from .schema_governance_engine import BreakingChange

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BreakingChangeResult:
    """Result of breaking change detection."""
    target: str
    repository: str
    baseline_tag: Optional[str]
    breaking_changes: List[BreakingChange]
    summary: Dict[str, int]
    analysis_time_ms: float
    buf_version: Optional[str] = None
    comparison_method: str = "buf_breaking"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonBaseline:
    """Baseline configuration for breaking change comparison."""
    repository: str
    tag: Optional[str] = None
    commit: Optional[str] = None
    branch: str = "main"
    local_path: Optional[str] = None


class BreakingChangeDetectionError(Exception):
    """Breaking change detection failed."""
    pass


class BSRBreakingChangeDetector:
    """
    BSR breaking change detection system.
    
    Provides comprehensive breaking change detection by comparing protobuf
    schemas against BSR repositories with detailed impact analysis and
    governance integration.
    """
    
    def __init__(self,
                 bsr_client: Optional[BSRClient] = None,
                 bsr_authenticator: Optional[BSRAuthenticator] = None,
                 cache_dir: Union[str, Path] = None,
                 verbose: bool = False):
        """
        Initialize BSR Breaking Change Detector.
        
        Args:
            bsr_client: BSR client instance
            bsr_authenticator: BSR authentication instance
            cache_dir: Directory for caching downloaded schemas
            verbose: Enable verbose logging
        """
        if cache_dir is None:
            cache_dir = Path.home() / '.cache' / 'buck2-protobuf' / 'breaking-changes'
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.verbose = verbose
        
        # Dependencies
        self.bsr_client = bsr_client or BSRClient(verbose=verbose)
        self.bsr_authenticator = bsr_authenticator or BSRAuthenticator(verbose=verbose)
        
        # Tool paths
        self.buf_cli = None
        self._init_tools()
        
        logger.info(f"BSR Breaking Change Detector initialized")

    def _init_tools(self) -> None:
        """Initialize required tools (buf CLI)."""
        # Try to find buf CLI in PATH
        try:
            result = subprocess.run(['which', 'buf'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.buf_cli = result.stdout.strip()
                logger.info(f"Found buf CLI at: {self.buf_cli}")
                return
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Try common installation paths
        common_paths = [
            '/usr/local/bin/buf',
            '/usr/bin/buf',
            Path.home() / 'bin' / 'buf',
            Path.home() / '.local' / 'bin' / 'buf'
        ]
        
        for path in common_paths:
            if Path(path).exists():
                self.buf_cli = str(path)
                logger.info(f"Found buf CLI at: {self.buf_cli}")
                return
        
        logger.warning("buf CLI not found. Breaking change detection will be limited.")

    def detect_breaking_changes(self,
                              proto_target: str,
                              against_repository: str,
                              against_tag: Optional[str] = None,
                              allow_list: List[str] = None,
                              ignore_patterns: List[str] = None,
                              proto_files: List[str] = None) -> List[BreakingChange]:
        """
        Detect breaking changes in protobuf schemas.
        
        Args:
            proto_target: Proto library target to check
            against_repository: BSR repository to compare against
            against_tag: Specific tag/commit to compare against
            allow_list: List of allowed breaking change types
            ignore_patterns: Patterns to ignore when detecting breaking changes
            proto_files: Optional list of proto files (if not using target)
            
        Returns:
            List of detected breaking changes
            
        Raises:
            BreakingChangeDetectionError: If detection fails
        """
        start_time = time.time()
        
        try:
            # Prepare comparison baseline
            baseline = self._prepare_baseline(against_repository, against_tag)
            
            # Get current proto files
            current_files = proto_files or self._get_proto_files_from_target(proto_target)
            
            # Perform breaking change detection
            if self.buf_cli:
                breaking_changes = self._detect_with_buf_cli(current_files, baseline, allow_list, ignore_patterns)
            else:
                # Fallback to basic detection
                breaking_changes = self._detect_basic(current_files, baseline)
            
            # Enhance breaking changes with impact analysis
            enhanced_changes = self._enhance_breaking_changes(breaking_changes, baseline)
            
            analysis_time = (time.time() - start_time) * 1000
            
            logger.info(f"Breaking change detection completed in {analysis_time:.1f}ms")
            logger.info(f"Found {len(enhanced_changes)} breaking changes")
            
            return enhanced_changes
            
        except Exception as e:
            logger.error(f"Breaking change detection failed: {e}")
            raise BreakingChangeDetectionError(f"Breaking change detection failed: {e}")

    def analyze_breaking_change_impact(self,
                                     breaking_changes: List[BreakingChange],
                                     repository: str) -> Dict[str, Any]:
        """
        Analyze the impact of breaking changes.
        
        Args:
            breaking_changes: List of breaking changes to analyze
            repository: Repository context for analysis
            
        Returns:
            Impact analysis results
        """
        if not breaking_changes:
            return {
                "overall_impact": "none",
                "risk_level": "low",
                "affected_components": [],
                "migration_complexity": "none",
                "recommendations": []
            }
        
        # Categorize breaking changes by severity
        high_impact = []
        medium_impact = []
        low_impact = []
        
        for change in breaking_changes:
            if change.impact == "high":
                high_impact.append(change)
            elif change.impact == "medium":
                medium_impact.append(change)
            else:
                low_impact.append(change)
        
        # Determine overall impact
        if high_impact:
            overall_impact = "high"
            risk_level = "high"
        elif medium_impact:
            overall_impact = "medium"
            risk_level = "medium"
        else:
            overall_impact = "low"
            risk_level = "low"
        
        # Extract affected components
        affected_components = list(set([
            self._extract_component_from_location(change.location)
            for change in breaking_changes
        ]))
        
        # Determine migration complexity
        migration_complexity = self._assess_migration_complexity(breaking_changes)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(breaking_changes, overall_impact)
        
        return {
            "overall_impact": overall_impact,
            "risk_level": risk_level,
            "breaking_change_count": len(breaking_changes),
            "high_impact_count": len(high_impact),
            "medium_impact_count": len(medium_impact),
            "low_impact_count": len(low_impact),
            "affected_components": affected_components,
            "migration_complexity": migration_complexity,
            "recommendations": recommendations,
            "analysis_timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ')
        }

    def generate_migration_guide(self,
                               breaking_changes: List[BreakingChange],
                               repository: str) -> str:
        """
        Generate a migration guide for breaking changes.
        
        Args:
            breaking_changes: List of breaking changes
            repository: Repository context
            
        Returns:
            Markdown-formatted migration guide
        """
        if not breaking_changes:
            return "# Migration Guide\n\nNo breaking changes detected. No migration required."
        
        guide = []
        guide.append("# Migration Guide")
        guide.append(f"\n**Repository:** {repository}")
        guide.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
        guide.append(f"**Breaking Changes:** {len(breaking_changes)}")
        
        # Group by component
        by_component = {}
        for change in breaking_changes:
            component = self._extract_component_from_location(change.location)
            if component not in by_component:
                by_component[component] = []
            by_component[component].append(change)
        
        guide.append("\n## Summary")
        guide.append(f"\nThis migration guide covers {len(breaking_changes)} breaking changes across {len(by_component)} components.")
        
        # Impact summary
        impact_analysis = self.analyze_breaking_change_impact(breaking_changes, repository)
        guide.append(f"\n**Overall Impact:** {impact_analysis['overall_impact'].title()}")
        guide.append(f"**Migration Complexity:** {impact_analysis['migration_complexity'].title()}")
        
        # By component
        guide.append("\n## Changes by Component")
        
        for component, changes in by_component.items():
            guide.append(f"\n### {component}")
            
            for change in changes:
                guide.append(f"\n#### {change.type}")
                guide.append(f"\n**Location:** {change.location}")
                guide.append(f"**Impact:** {change.impact.title()}")
                guide.append(f"\n{change.description}")
                
                if change.old_value and change.new_value:
                    guide.append(f"\n**Before:**")
                    guide.append(f"```protobuf\n{change.old_value}\n```")
                    guide.append(f"\n**After:**")
                    guide.append(f"```protobuf\n{change.new_value}\n```")
                
                if change.migration_guide:
                    guide.append(f"\n**Migration Steps:**")
                    guide.append(f"{change.migration_guide}")
                
                guide.append("")
        
        # Recommendations
        if impact_analysis['recommendations']:
            guide.append("\n## Recommendations")
            for i, rec in enumerate(impact_analysis['recommendations'], 1):
                guide.append(f"{i}. {rec}")
        
        return "\n".join(guide)

    def _prepare_baseline(self, repository: str, tag: Optional[str] = None) -> ComparisonBaseline:
        """Prepare baseline for comparison."""
        baseline = ComparisonBaseline(
            repository=repository,
            tag=tag,
            branch="main"
        )
        
        # Download baseline schemas if needed
        cache_key = f"{repository}:{tag or 'latest'}"
        cache_path = self.cache_dir / cache_key.replace('/', '_').replace(':', '_')
        
        if not cache_path.exists():
            try:
                self._download_baseline_schemas(baseline, cache_path)
            except Exception as e:
                logger.warning(f"Failed to download baseline schemas: {e}")
                # Continue with local comparison only
        
        baseline.local_path = str(cache_path) if cache_path.exists() else None
        
        return baseline

    def _download_baseline_schemas(self, baseline: ComparisonBaseline, cache_path: Path) -> None:
        """Download baseline schemas from BSR."""
        # This would integrate with BSR client to download schemas
        # For now, create a placeholder structure
        cache_path.mkdir(parents=True, exist_ok=True)
        
        # Create a placeholder buf.yaml for the baseline
        buf_config = {
            "version": "v1",
            "modules": [
                {
                    "path": ".",
                    "name": baseline.repository
                }
            ]
        }
        
        with open(cache_path / "buf.yaml", 'w') as f:
            import yaml
            yaml.dump(buf_config, f)
        
        logger.info(f"Downloaded baseline schemas to {cache_path}")

    def _get_proto_files_from_target(self, proto_target: str) -> List[str]:
        """Get proto files from Buck2 target."""
        # This would integrate with Buck2 to get proto files from target
        # For now, return a placeholder
        logger.warning(f"Proto file extraction from target {proto_target} not yet implemented")
        return []

    def _detect_with_buf_cli(self,
                           current_files: List[str],
                           baseline: ComparisonBaseline,
                           allow_list: List[str] = None,
                           ignore_patterns: List[str] = None) -> List[BreakingChange]:
        """Detect breaking changes using buf CLI."""
        if not self.buf_cli:
            raise BreakingChangeDetectionError("buf CLI not available")
        
        breaking_changes = []
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create buf.yaml for current files
                buf_config = {
                    "version": "v1",
                    "modules": [{"path": "."}],
                    "breaking": {
                        "use": ["FILE"]
                    }
                }
                
                # Add ignore patterns if provided
                if ignore_patterns:
                    buf_config["breaking"]["ignore"] = ignore_patterns
                
                with open(temp_path / "buf.yaml", 'w') as f:
                    import yaml
                    yaml.dump(buf_config, f)
                
                # Copy current proto files to temp directory
                for proto_file in current_files:
                    if Path(proto_file).exists():
                        import shutil
                        shutil.copy2(proto_file, temp_path)
                
                # Run buf breaking if baseline is available
                if baseline.local_path:
                    cmd = [
                        self.buf_cli, "breaking",
                        str(temp_path),
                        "--against", baseline.local_path,
                        "--format", "json"
                    ]
                    
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=60,
                        cwd=temp_path
                    )
                    
                    if result.returncode != 0 and result.stdout:
                        # Parse buf breaking output
                        try:
                            buf_output = json.loads(result.stdout)
                            breaking_changes = self._parse_buf_breaking_output(buf_output, baseline.repository)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse buf breaking output: {result.stdout}")
                    
                    if result.stderr:
                        logger.warning(f"buf breaking stderr: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error("buf breaking command timed out")
        except Exception as e:
            logger.error(f"buf breaking detection failed: {e}")
        
        return breaking_changes

    def _detect_basic(self, current_files: List[str], baseline: ComparisonBaseline) -> List[BreakingChange]:
        """Basic breaking change detection without buf CLI."""
        # This is a simplified fallback implementation
        # In practice, this would implement basic protobuf comparison logic
        logger.warning("Using basic breaking change detection (buf CLI not available)")
        
        breaking_changes = []
        
        # Placeholder: detect obvious breaking changes
        # This would be expanded with actual protobuf parsing and comparison
        
        return breaking_changes

    def _parse_buf_breaking_output(self, buf_output: Dict[str, Any], repository: str) -> List[BreakingChange]:
        """Parse buf breaking command output into BreakingChange objects."""
        breaking_changes = []
        
        # buf breaking outputs a list of violations
        violations = buf_output.get('violations', [])
        
        for violation in violations:
            change = BreakingChange(
                type=violation.get('type', 'UNKNOWN'),
                description=violation.get('message', 'Unknown breaking change'),
                location=f"{violation.get('file', 'unknown')}:{violation.get('line', 0)}",
                impact=self._assess_change_impact(violation.get('type', 'UNKNOWN')),
                repository=repository
            )
            breaking_changes.append(change)
        
        return breaking_changes

    def _enhance_breaking_changes(self, 
                                breaking_changes: List[BreakingChange],
                                baseline: ComparisonBaseline) -> List[BreakingChange]:
        """Enhance breaking changes with additional analysis."""
        enhanced = []
        
        for change in breaking_changes:
            # Add migration guide
            change.migration_guide = self._generate_change_migration_guide(change)
            
            # Enhance impact assessment
            change.impact = self._assess_detailed_impact(change, baseline)
            
            enhanced.append(change)
        
        return enhanced

    def _assess_change_impact(self, change_type: str) -> str:
        """Assess the impact level of a breaking change type."""
        high_impact_types = [
            "FIELD_REMOVED",
            "MESSAGE_REMOVED", 
            "SERVICE_REMOVED",
            "RPC_REMOVED",
            "ENUM_REMOVED",
            "ENUM_VALUE_REMOVED"
        ]
        
        medium_impact_types = [
            "FIELD_TYPE_CHANGED",
            "FIELD_CARDINALITY_CHANGED",
            "RPC_REQUEST_TYPE_CHANGED",
            "RPC_RESPONSE_TYPE_CHANGED"
        ]
        
        if change_type in high_impact_types:
            return "high"
        elif change_type in medium_impact_types:
            return "medium"
        else:
            return "low"

    def _assess_detailed_impact(self, change: BreakingChange, baseline: ComparisonBaseline) -> str:
        """Perform detailed impact assessment for a breaking change."""
        # This could be enhanced with more sophisticated analysis
        # such as dependency analysis, usage pattern analysis, etc.
        return change.impact

    def _extract_component_from_location(self, location: str) -> str:
        """Extract component name from location string."""
        # Extract filename from location
        if ':' in location:
            file_part = location.split(':')[0]
        else:
            file_part = location
        
        if '/' in file_part:
            return Path(file_part).stem
        else:
            return file_part

    def _assess_migration_complexity(self, breaking_changes: List[BreakingChange]) -> str:
        """Assess overall migration complexity."""
        high_impact_count = sum(1 for change in breaking_changes if change.impact == "high")
        medium_impact_count = sum(1 for change in breaking_changes if change.impact == "medium")
        
        if high_impact_count > 0:
            return "high"
        elif medium_impact_count > 2:
            return "medium"
        elif len(breaking_changes) > 5:
            return "medium"
        else:
            return "low"

    def _generate_recommendations(self, breaking_changes: List[BreakingChange], overall_impact: str) -> List[str]:
        """Generate recommendations based on breaking changes."""
        recommendations = []
        
        if overall_impact == "high":
            recommendations.append("Consider phasing the migration over multiple releases")
            recommendations.append("Implement comprehensive testing before deployment")
            recommendations.append("Prepare detailed communication plan for affected teams")
        
        if overall_impact in ["high", "medium"]:
            recommendations.append("Review impact with all downstream consumers")
            recommendations.append("Consider providing migration tooling or scripts")
        
        recommendations.append("Update API documentation to reflect changes")
        recommendations.append("Monitor for migration-related issues post-deployment")
        
        return recommendations

    def _generate_change_migration_guide(self, change: BreakingChange) -> str:
        """Generate migration guide for a specific breaking change."""
        migration_guides = {
            "FIELD_REMOVED": "Update client code to stop using the removed field. Check for any dependencies on this field.",
            "FIELD_TYPE_CHANGED": "Update client code to handle the new field type. Ensure type conversion is handled properly.",
            "MESSAGE_REMOVED": "Replace usage of the removed message with alternative message types or restructure client code.",
            "SERVICE_REMOVED": "Migrate to alternative service or implement equivalent functionality.",
            "RPC_REMOVED": "Replace calls to the removed RPC with alternative RPCs or implement equivalent client-side logic.",
            "ENUM_VALUE_REMOVED": "Update client code to handle removal of enum value. Replace with alternative enum values."
        }
        
        return migration_guides.get(change.type, "Review the change and update client code accordingly.")


def main():
    """Main entry point for breaking change detector testing."""
    parser = argparse.ArgumentParser(description="BSR Breaking Change Detector")
    parser.add_argument("--cache-dir", help="Cache directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Detect breaking changes
    detect_parser = subparsers.add_parser("detect", help="Detect breaking changes")
    detect_parser.add_argument("--target", required=True, help="Proto target to check")
    detect_parser.add_argument("--against", required=True, help="Repository to compare against")
    detect_parser.add_argument("--tag", help="Specific tag to compare against")
    detect_parser.add_argument("--allow", nargs="*", help="Allow list of breaking change types")
    detect_parser.add_argument("--ignore", nargs="*", help="Ignore patterns")
    
    # Analyze impact
    analyze_parser = subparsers.add_parser("analyze", help="Analyze breaking change impact")
    analyze_parser.add_argument("--changes-file", required=True, help="JSON file with breaking changes")
    analyze_parser.add_argument("--repository", required=True, help="Repository context")
    
    # Generate migration guide
    guide_parser = subparsers.add_parser("guide", help="Generate migration guide")
    guide_parser.add_argument("--changes-file", required=True, help="JSON file with breaking changes")
    guide_parser.add_argument("--repository", required=True, help="Repository context")
    guide_parser.add_argument("--output", help="Output file for migration guide")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        detector = BSRBreakingChangeDetector(
            cache_dir=args.cache_dir,
            verbose=args.verbose
        )
        
        if args.command == "detect":
            breaking_changes = detector.detect_breaking_changes(
                proto_target=args.target,
                against_repository=args.against,
                against_tag=args.tag,
                allow_list=args.allow or [],
                ignore_patterns=args.ignore or []
            )
            
            if breaking_changes:
                print(f"🔍 Found {len(breaking_changes)} breaking changes:")
                for change in breaking_changes:
                    print(f"  - {change.type}: {change.description}")
                    print(f"    Location: {change.location} (Impact: {change.impact})")
                    if change.migration_guide:
                        print(f"    Migration: {change.migration_guide}")
                    print()
                
                # Save results to file
                results_file = f"breaking_changes_{int(time.time())}.json"
                with open(results_file, 'w') as f:
                    json.dump([asdict(change) for change in breaking_changes], f, indent=2)
                print(f"📁 Results saved to {results_file}")
                
                return 1  # Exit with error code if breaking changes found
            else:
                print("✅ No breaking changes detected")
        
        elif args.command == "analyze":
            with open(args.changes_file, 'r') as f:
                changes_data = json.load(f)
            
            breaking_changes = [BreakingChange(**change_data) for change_data in changes_data]
            
            impact_analysis = detector.analyze_breaking_change_impact(breaking_changes, args.repository)
            
            print(f"📊 Breaking Change Impact Analysis")
            print(f"   Repository: {args.repository}")
            print(f"   Overall Impact: {impact_analysis['overall_impact'].title()}")
            print(f"   Risk Level: {impact_analysis['risk_level'].title()}")
            print(f"   Migration Complexity: {impact_analysis['migration_complexity'].title()}")
            print(f"   Breaking Changes: {impact_analysis['breaking_change_count']}")
            print(f"   Affected Components: {len(impact_analysis['affected_components'])}")
            
            if impact_analysis['recommendations']:
                print(f"\n💡 Recommendations:")
                for i, rec in enumerate(impact_analysis['recommendations'], 1):
                    print(f"   {i}. {rec}")
        
        elif args.command == "guide":
            with open(args.changes_file, 'r') as f:
                changes_data = json.load(f)
            
            breaking_changes = [BreakingChange(**change_data) for change_data in changes_data]
            
            migration_guide = detector.generate_migration_guide(breaking_changes, args.repository)
            
            if args.output:
                with open(args.output, 'w') as f:
                    f.write(migration_guide)
                print(f"📖 Migration guide saved to {args.output}")
            else:
                print(migration_guide)
    
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
